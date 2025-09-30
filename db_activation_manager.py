#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 PostgreSQL 的激活码管理器
自动处理数据库连接和表初始化
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class DatabaseActivationManager:
    """使用 PostgreSQL 存储激活码"""

    def __init__(self, database_url: str):
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("需要安装 psycopg2-binary: pip install psycopg2-binary")

        self.database_url = database_url
        self._init_database()
        print("[激活码管理] 使用 PostgreSQL 数据库持久化")

    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(self.database_url)

    def _init_database(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS activation_codes (
                        code VARCHAR(50) PRIMARY KEY,
                        max_voices INTEGER NOT NULL DEFAULT 0,
                        used_voices INTEGER NOT NULL DEFAULT 0,
                        max_characters INTEGER NOT NULL DEFAULT 0,
                        used_characters INTEGER NOT NULL DEFAULT 0,
                        expires_at DATE,
                        disabled BOOLEAN NOT NULL DEFAULT FALSE,
                        note TEXT DEFAULT '',
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        last_used_at TIMESTAMP
                    )
                """)
                conn.commit()

    def get_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """获取激活码信息"""
        code = (code or "").upper()
        if not code:
            return None

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM activation_codes WHERE code = %s
                """, (code,))
                row = cur.fetchone()

                if not row:
                    return None

                return self._build_info(dict(row))

    def list_codes(self) -> List[Dict[str, Any]]:
        """列出所有激活码"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM activation_codes ORDER BY created_at DESC
                """)
                rows = cur.fetchall()
                return [self._build_info(dict(row)) for row in rows]

    def create_code(self, max_voices: int, max_characters: int,
                   expires_at: Optional[str], note: str = "") -> Dict[str, Any]:
        """创建新激活码"""
        from activation_manager import ActivationManager
        from pathlib import Path

        # 使用原有的代码生成逻辑
        temp_manager = ActivationManager(Path("temp_codes.json"))
        new_code = temp_manager._generate_unique_code(set())

        # 解析过期日期
        expiry_date = None
        if expires_at:
            try:
                expiry_date = datetime.strptime(expires_at, "%Y-%m-%d").date()
            except ValueError:
                pass

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO activation_codes
                    (code, max_voices, used_voices, max_characters, used_characters,
                     expires_at, disabled, note, created_at)
                    VALUES (%s, %s, 0, %s, 0, %s, FALSE, %s, NOW())
                    RETURNING *
                """, (new_code, max(int(max_voices), 0), max(int(max_characters), 0),
                      expiry_date, note or ""))
                row = cur.fetchone()
                conn.commit()
                return self._build_info(dict(row))

    def update_code(self, code: str, *, max_voices: Optional[int] = None,
                   max_characters: Optional[int] = None, expires_at: Optional[str] = None,
                   note: Optional[str] = None, disabled: Optional[bool] = None) -> Dict[str, Any]:
        """更新激活码"""
        code = (code or "").upper()
        updates = []
        params = []

        if max_voices is not None:
            updates.append("max_voices = %s")
            params.append(max(int(max_voices), 0))
            updates.append("used_voices = LEAST(used_voices, %s)")
            params.append(max(int(max_voices), 0))

        if max_characters is not None:
            updates.append("max_characters = %s")
            params.append(max(int(max_characters), 0))
            updates.append("used_characters = LEAST(used_characters, %s)")
            params.append(max(int(max_characters), 0))

        if expires_at is not None:
            try:
                expiry_date = datetime.strptime(expires_at.strip(), "%Y-%m-%d").date() if expires_at.strip() else None
                updates.append("expires_at = %s")
                params.append(expiry_date)
            except ValueError:
                pass

        if note is not None:
            updates.append("note = %s")
            params.append(note)

        if disabled is not None:
            updates.append("disabled = %s")
            params.append(bool(disabled))

        if not updates:
            return self.get_code_info(code)

        params.append(code)

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    UPDATE activation_codes
                    SET {', '.join(updates)}
                    WHERE code = %s
                    RETURNING *
                """, params)
                row = cur.fetchone()
                conn.commit()

                if not row:
                    raise RuntimeError("激活码不存在")

                return self._build_info(dict(row))

    def record_usage(self, code: str, characters: int, created_voice: bool) -> Dict[str, Any]:
        """记录使用情况"""
        code = (code or "").upper()

        updates = ["last_used_at = NOW()"]
        params = []

        if created_voice:
            updates.append("used_voices = used_voices + 1")

        if characters > 0:
            updates.append("used_characters = used_characters + %s")
            params.append(int(characters))

        params.append(code)

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    UPDATE activation_codes
                    SET {', '.join(updates)}
                    WHERE code = %s
                    RETURNING *
                """, params)
                row = cur.fetchone()
                conn.commit()

                if not row:
                    raise RuntimeError("激活码不存在")

                return self._build_info(dict(row))

    def ensure_quota(self, code: str, required_characters: int,
                    needs_new_voice: bool) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """检查配额"""
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

    def _build_info(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """构建激活码信息字典"""
        today = datetime.utcnow().date()
        expires_at = row.get("expires_at")
        expired = expires_at is not None and today > expires_at

        max_voices = row.get("max_voices", 0) or 0
        used_voices = row.get("used_voices", 0) or 0
        available_voices = None if max_voices == 0 else max(max_voices - used_voices, 0)

        max_characters = row.get("max_characters", 0) or 0
        used_characters = row.get("used_characters", 0) or 0
        remaining_characters = None if max_characters == 0 else max(max_characters - used_characters, 0)

        created_at = row.get("created_at")
        last_used_at = row.get("last_used_at")

        return {
            "code": row["code"],
            "max_voices": max_voices,
            "used_voices": used_voices,
            "available_voices": available_voices,
            "max_characters": max_characters,
            "used_characters": used_characters,
            "remaining_characters": remaining_characters,
            "expires_at": expires_at.isoformat() if isinstance(expires_at, date) else expires_at,
            "expired": expired,
            "disabled": row.get("disabled", False),
            "note": row.get("note", ""),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            "last_used_at": last_used_at.isoformat() if isinstance(last_used_at, datetime) else last_used_at,
        }