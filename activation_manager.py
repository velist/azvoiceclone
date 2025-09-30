from __future__ import annotations

import json
import secrets
import string
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ActivationError(Exception):
    """Raised when activation operations fail."""


class ActivationManager:
    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        if self.storage_path.is_dir():
            raise ActivationError("storage_path must point to a file")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        if not self.storage_path.exists():
            # 尝试从环境变量加载默认激活码（用于 Render 等临时文件系统）
            import os
            default_codes_json = os.getenv("DEFAULT_ACTIVATION_CODES")
            if default_codes_json:
                try:
                    default_data = json.loads(default_codes_json)
                    if isinstance(default_data, dict) and "codes" in default_data:
                        print(f"[激活码管理] 从环境变量加载了 {len(default_data['codes'])} 个默认激活码")
                        self._save_data(default_data)
                        return
                except json.JSONDecodeError:
                    print("[激活码管理] 警告：DEFAULT_ACTIVATION_CODES 环境变量格式错误")
            self._save_data({"codes": {}})

    def _load_data(self) -> Dict[str, Any]:
        if not self.storage_path.exists():
            return {"codes": {}}
        try:
            raw_text = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(raw_text) if raw_text.strip() else {"codes": {}}
        except (OSError, json.JSONDecodeError):
            return {"codes": {}}
        codes = data.get("codes")
        if not isinstance(codes, dict):
            return {"codes": {}}
        normalised = {
            code.upper(): self._normalise_record(code.upper(), record)
            for code, record in codes.items()
        }
        return {"codes": normalised}

    def _save_data(self, data: Dict[str, Any]) -> None:
        payload = {"codes": data.get("codes", {})}
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _normalise_record(self, code: str, record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        record = dict(record or {})
        record["code"] = code.upper()
        for key in ("max_voices", "used_voices", "max_characters", "used_characters"):
            try:
                record[key] = max(int(record.get(key, 0)), 0)
            except (TypeError, ValueError):
                record[key] = 0
        record["note"] = str(record.get("note") or "").strip()
        record["disabled"] = bool(record.get("disabled", False))
        record["created_at"] = self._safe_iso(record.get("created_at")) or datetime.utcnow().isoformat()
        record["last_used_at"] = self._safe_iso(record.get("last_used_at"))
        record["expires_at"] = self._format_expiry(record.get("expires_at"))
        return record

    def _safe_iso(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        try:
            datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        return value

    def _format_expiry(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        expiry = self._parse_expiry(value)
        return expiry.isoformat() if expiry else None

    def _parse_expiry(self, value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        try:
            if len(value) == 10:
                return datetime.strptime(value, "%Y-%m-%d").date()
            return datetime.fromisoformat(value).date()
        except (TypeError, ValueError):
            return None

    def _build_info(self, record: Dict[str, Any]) -> Dict[str, Any]:
        expiry_str = record.get("expires_at")
        expiry_date = self._parse_expiry(expiry_str)
        today = datetime.utcnow().date()
        expired = expiry_date is not None and today > expiry_date

        max_voices = max(int(record.get("max_voices", 0) or 0), 0)
        used_voices = max(int(record.get("used_voices", 0) or 0), 0)
        available_voices = None if max_voices == 0 else max(max_voices - used_voices, 0)

        max_characters = max(int(record.get("max_characters", 0) or 0), 0)
        used_characters = max(int(record.get("used_characters", 0) or 0), 0)
        remaining_characters = None if max_characters == 0 else max(max_characters - used_characters, 0)

        return {
            "code": record["code"],
            "max_voices": max_voices,
            "used_voices": used_voices,
            "available_voices": available_voices,
            "max_characters": max_characters,
            "used_characters": used_characters,
            "remaining_characters": remaining_characters,
            "expires_at": expiry_date.isoformat() if expiry_date else None,
            "expired": expired,
            "disabled": bool(record.get("disabled", False)),
            "note": record.get("note", ""),
            "created_at": record.get("created_at"),
            "last_used_at": record.get("last_used_at"),
        }

    def get_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        code = (code or "").upper()
        if not code:
            return None
        data = self._load_data()
        record = data["codes"].get(code)
        if not record:
            return None
        return self._build_info(record)

    def list_codes(self) -> List[Dict[str, Any]]:
        data = self._load_data()
        infos = [self._build_info(record) for record in data["codes"].values()]
        return sorted(infos, key=lambda item: item.get("created_at") or "", reverse=True)

    def ensure_quota(self, code: str, required_characters: int, needs_new_voice: bool) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        info = self.get_code_info(code)
        if not info:
            return False, "激活码不存在或已被删除。", None
        if info["disabled"]:
            return False, "激活码已停用，请联系管理员。", info
        if info["expired"]:
            return False, "激活码已过期，请联系管理员。", info
        if needs_new_voice and info["available_voices"] is not None and info["available_voices"] <= 0:
            return False, "可用音色额度不足，请联系管理员。", info
        if required_characters > 0 and info["remaining_characters"] is not None and info["remaining_characters"] < required_characters:
            return False, "剩余字符不足，请缩短文本或联系管理员。", info
        return True, "", info

    def record_usage(self, code: str, characters: int, created_voice: bool) -> Dict[str, Any]:
        code = (code or "").upper()
        data = self._load_data()
        record = data["codes"].get(code)
        if not record:
            raise ActivationError("激活码不存在。")
        if created_voice:
            record["used_voices"] = int(record.get("used_voices", 0) or 0) + 1
        if characters > 0:
            record["used_characters"] = int(record.get("used_characters", 0) or 0) + int(characters)
        if record.get("max_voices", 0) > 0:
            record["used_voices"] = min(record["used_voices"], record["max_voices"])
        if record.get("max_characters", 0) > 0:
            record["used_characters"] = min(record["used_characters"], record["max_characters"])
        record["last_used_at"] = datetime.utcnow().isoformat()
        data["codes"][code] = self._normalise_record(code, record)
        self._save_data(data)
        return self._build_info(data["codes"][code])

    def create_code(self, max_voices: int, max_characters: int, expires_at: Optional[str], note: str = "") -> Dict[str, Any]:
        data = self._load_data()
        new_code = self._generate_unique_code(set(data["codes"].keys()))
        record = {
            "max_voices": max(int(max_voices), 0),
            "used_voices": 0,
            "max_characters": max(int(max_characters), 0),
            "used_characters": 0,
            "expires_at": expires_at,
            "note": note or "",
            "disabled": False,
            "created_at": datetime.utcnow().isoformat(),
            "last_used_at": None,
        }
        data["codes"][new_code] = self._normalise_record(new_code, record)
        self._save_data(data)
        return self._build_info(data["codes"][new_code])

    def update_code(
        self,
        code: str,
        *,
        max_voices: Optional[int] = None,
        max_characters: Optional[int] = None,
        expires_at: Optional[str] = None,
        note: Optional[str] = None,
        disabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        code = (code or "").upper()
        data = self._load_data()
        if code not in data["codes"]:
            raise ActivationError("激活码不存在。")
        record = data["codes"][code]
        if max_voices is not None:
            record["max_voices"] = max(int(max_voices), 0)
            if record["max_voices"] == 0:
                record["used_voices"] = int(record.get("used_voices", 0) or 0)
            else:
                record["used_voices"] = min(int(record.get("used_voices", 0) or 0), record["max_voices"])
        if max_characters is not None:
            record["max_characters"] = max(int(max_characters), 0)
            if record["max_characters"] == 0:
                record["used_characters"] = int(record.get("used_characters", 0) or 0)
            else:
                record["used_characters"] = min(int(record.get("used_characters", 0) or 0), record["max_characters"])
        if expires_at is not None:
            record["expires_at"] = expires_at
        if note is not None:
            record["note"] = note
        if disabled is not None:
            record["disabled"] = bool(disabled)
        data["codes"][code] = self._normalise_record(code, record)
        self._save_data(data)
        return self._build_info(data["codes"][code])

    def _generate_unique_code(self, existing: set[str], length: int = 16) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            candidate = "".join(secrets.choice(alphabet) for _ in range(length))
            if candidate not in existing:
                return candidate