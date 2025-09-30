from __future__ import annotations

import base64
import datetime
import mimetypes
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import requests
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import uvicorn

import config
from activation_manager import ActivationError, ActivationManager


REQUEST_TIMEOUT = (10, 120)
MAX_REFERENCE_FILE_SIZE_MB = 10

CUSTOM_CSS = """
footer {display: none !important;}
#share-btn-container {display: none !important;}
button[data-testid="block-info"] {display: none !important;}
button[data-testid="view-api"] {display: none !important;}
div[data-testid="block-info"] {display: none !important;}
"""

ACTIVATION_MANAGER = ActivationManager(config.ACTIVATION_STORE_PATH)

ADVANCED_PRESETS = {
    "魔搭示例": {
        "do_sample": True,
        "temperature": 0.72,
        "top_p": 0.86,
        "top_k": 40,
        "repetition_penalty": 9.0,
        "length_penalty": 0.0,
        "num_beams": 4,
        "max_mel_tokens": 1600,
        "emotion_text": "充满活力",
        "emo_alpha": 0.9,
    },
    "通用默认": {
        "do_sample": True,
        "temperature": 0.8,
        "top_p": 0.8,
        "top_k": 30,
        "repetition_penalty": 10.0,
        "length_penalty": 0.0,
        "num_beams": 3,
        "max_mel_tokens": 1500,
        "emotion_text": "",
        "emo_alpha": 1.0,
    },
}

DEFAULT_PRESET = "魔搭示例"

EMOTION_MODE_OPTIONS = [
    "与音色参考音频相同",
    "使用情感参考音频",
    "使用情感向量控制",
    "使用情感描述文本控制",
]

EMOTION_VECTOR_LABELS = [
    "高兴",
    "愤怒",
    "悲伤",
    "害怕",
    "厌恶",
    "忧郁",
    "惊讶",
    "平静",
]

def _advanced_preset_values(preset_name: str) -> Tuple[bool, float, float, float, float, float, float, float, str, float]:
    preset = ADVANCED_PRESETS.get(preset_name) or ADVANCED_PRESETS[DEFAULT_PRESET]
    return (
        bool(preset.get("do_sample", True)),
        float(preset.get("temperature", 0.8)),
        float(preset.get("top_p", 0.8)),
        float(preset.get("top_k", 30)),
        float(preset.get("repetition_penalty", 10.0)),
        float(preset.get("length_penalty", 0.0)),
        float(preset.get("num_beams", 3)),
        float(preset.get("max_mel_tokens", 1500)),
        preset.get("emotion_text", ""),
        float(preset.get("emo_alpha", 1.0)),
    )


def apply_advanced_preset(preset_name: str):
    return _advanced_preset_values(preset_name)


def apply_clone_preset(preset_name: str):
    (
        do_sample,
        temperature,
        top_p,
        top_k,
        repetition_penalty,
        length_penalty,
        num_beams,
        max_mel_tokens,
        emotion_text,
        emo_alpha,
    ) = _advanced_preset_values(preset_name)

    emotion_mode = EMOTION_MODE_OPTIONS[3] if emotion_text else EMOTION_MODE_OPTIONS[0]

    return (
        emotion_mode,
        bool(do_sample),
        float(temperature),
        float(top_p),
        float(top_k),
        float(repetition_penalty),
        float(length_penalty),
        float(num_beams),
        float(max_mel_tokens),
        emotion_text,
        float(emo_alpha),
    )


def apply_clone_preset_wrapper(preset_name: str):
    return apply_clone_preset(preset_name)

def _save_audio(content: bytes, response_format: str) -> str:
    suffix = f".{response_format.lower()}" if response_format else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(content)
        return tmp_file.name


def _call_siliconflow(payload: Dict[str, Any]) -> Tuple[Optional[str], str]:
    api_key = config.get_api_key()
    if not api_key:
        return None, "API 密钥未配置，请编辑 siliconflowkey.env。"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response_format = payload.get("response_format", "mp3") or "mp3"

    try:
        response = requests.post(
            config.API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return None, "请求超时，请稍后重试。"
    except requests.exceptions.RequestException as exc:
        return None, f"请求失败：{exc}"

    if response.status_code == 200:
        file_path = _save_audio(response.content, response_format)
        print(
            "[SiliconFlow] 请求成功",
            f"模型={payload.get('model')}",
            f"音频字节数={len(response.content)}",
        )
        return file_path, "生成成功。"

    try:
        error_detail = response.json()
    except ValueError:
        error_detail = response.text[:500]

    print(
        "[SiliconFlow] 请求失败",
        f"状态码={response.status_code}",
        f"详情={error_detail}",
    )
    return None, f"生成失败（HTTP {response.status_code}）：{error_detail}"

def _build_custom_name(raw_name: str) -> str:
    if raw_name:
        sanitized = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in raw_name.strip()
        )
        sanitized = "-".join(filter(None, sanitized.split("-")))
        if sanitized:
            return sanitized[:60]
    return datetime.datetime.now().strftime("clone-%Y%m%d-%H%M%S")


def _upload_reference_audio(
    audio_path: str,
    api_key: str,
    custom_name: str,
    sample_text: str,
) -> Tuple[Optional[str], Optional[str]]:
    if not os.path.exists(audio_path):
        return None, "未找到参考音频文件。"

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb > MAX_REFERENCE_FILE_SIZE_MB:
        return None, f"参考音频不能超过 {MAX_REFERENCE_FILE_SIZE_MB} MB。"

    headers = {"Authorization": f"Bearer {api_key}"}
    mime_type, _ = mimetypes.guess_type(audio_path)
    mime_type = mime_type or "application/octet-stream"

    data = {
        "model": config.MODEL_NAME,
        "customName": custom_name,
    }
    sample_text = (sample_text or "").strip()
    if sample_text:
        data["text"] = sample_text[:200]

    try:
        with open(audio_path, "rb") as audio_file:
            files = {"file": (os.path.basename(audio_path), audio_file, mime_type)}
            response = requests.post(
                config.VOICE_UPLOAD_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=REQUEST_TIMEOUT,
            )
    except requests.exceptions.Timeout:
        return None, "上传参考音频超时，请稍后重试。"
    except requests.exceptions.RequestException as exc:
        return None, f"上传参考音频失败：{exc}"
    except OSError as exc:
        return None, f"读取音频文件失败：{exc}"

    if response.status_code != 200:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        return None, f"上传参考音频失败（HTTP {response.status_code}）：{detail}"

    try:
        payload = response.json()
    except ValueError:
        return None, "上传返回结果不是有效的 JSON。"

    voice_uri = payload.get("uri")
    if not voice_uri:
        return None, "上传成功，但未返回音色 URI，请检查账号权限。"

    return voice_uri, None


def _encode_audio_for_payload(audio_path: str, label: str) -> Tuple[Optional[str], Optional[str]]:
    if not os.path.exists(audio_path):
        return None, f"{label}未找到。"

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb > MAX_REFERENCE_FILE_SIZE_MB:
        return None, f"{label}不能超过 {MAX_REFERENCE_FILE_SIZE_MB} MB。"

    try:
        with open(audio_path, "rb") as audio_file:
            encoded = base64.b64encode(audio_file.read()).decode("utf-8")
            return encoded, None
    except OSError as exc:
        return None, f"读取{label}失败：{exc}"


def update_emotion_mode_controls(mode: str):
    use_audio = mode == EMOTION_MODE_OPTIONS[1]
    use_vector = mode == EMOTION_MODE_OPTIONS[2]
    use_text = mode == EMOTION_MODE_OPTIONS[3]

    audio_update = gr.update(visible=use_audio)
    vector_updates = [gr.update(visible=use_vector) for _ in EMOTION_VECTOR_LABELS]
    text_update = gr.update(visible=use_text)

    return (audio_update, *vector_updates, text_update)

def text_to_speech(
    text: str,
    voice_id: str,
    speed: float,
    pitch: float,
    volume: float,
    response_format: str,
    do_sample: bool,
    temperature: float,
    top_p: float,
    top_k: float,
    repetition_penalty: float,
    length_penalty: float,
    num_beams: float,
    max_mel_tokens: float,
    emotion_text: str,
    emo_alpha: float,
) -> Tuple[Optional[str], str]:
    text = (text or "").strip()
    if not text:
        return None, "请输入要转换的文本。"

    voice_id = (voice_id or "").strip()
    if not voice_id:
        return None, "请填写 IndexTTS2 的音色 ID。"

    payload = {
        "model": config.MODEL_NAME,
        "input": text,
        "voice": voice_id,
        "response_format": response_format or "mp3",
        "speed": speed,
        "pitch": pitch,
        "volume": volume,
        "do_sample": bool(do_sample),
        "temperature": temperature,
        "top_p": top_p,
        "top_k": int(top_k),
        "repetition_penalty": repetition_penalty,
        "length_penalty": length_penalty,
        "num_beams": int(num_beams),
        "max_mel_tokens": int(max_mel_tokens),
        "emo_alpha": emo_alpha,
    }

    emotion_text = (emotion_text or "").strip()
    if emotion_text:
        payload["emotion_text"] = emotion_text

    audio_path, status = _call_siliconflow(payload)

    param_summary = (
        f"采样={'开' if do_sample else '关'}, temperature={temperature}, top_p={top_p}, top_k={int(top_k)}, "
        f"重复惩罚={repetition_penalty}, num_beams={int(num_beams)}, 最大Mel={int(max_mel_tokens)}, 情感强度={emo_alpha}"
    )
    if emotion_text:
        param_summary += f"，情感描述='{emotion_text}'"

    status = f"{status}\n{param_summary}"

    return audio_path, status

def mask_activation_code(code: str, reveal_full: bool) -> str:
    code = (code or "").strip()
    if not code:
        return ""
    if reveal_full:
        return code
    if len(code) <= 4:
        return "***"
    prefix = code[:4]
    suffix = code[-4:] if len(code) > 8 else code[-2:]
    middle_length = max(len(code) - len(prefix) - len(suffix), 3)
    return f"{prefix}{'*' * middle_length}{suffix}"


def _format_datetime(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%Y-%m-%d %H:%M")


def format_activation_summary(info: Optional[Dict[str, Any]], reveal_full: bool) -> str:
    if not info or not info.get("code"):
        return "🔒 请先输入激活码完成登录。"

    code_display = mask_activation_code(info["code"], reveal_full)

    if info.get("max_voices", 0) == 0:
        voice_text = "无限额度"
    else:
        voice_text = f"{info.get('available_voices', 0)} / {info.get('max_voices', 0)}"

    if info.get("max_characters", 0) == 0:
        char_text = "无限字符"
    else:
        char_text = f"{info.get('remaining_characters', 0)} / {info.get('max_characters', 0)}"

    expires = info.get("expires_at") or "长期有效"
    status_flags: List[str] = []
    if info.get("disabled"):
        status_flags.append("已停用")
    if info.get("expired"):
        status_flags.append("已过期")
    if not status_flags:
        status_flags.append("正常")

    lines = [
        f"**激活码**：`{code_display}`",
        f"- 可用音色额度：{voice_text}",
        f"- 剩余字符数：{char_text}",
        f"- 有效期：{expires}",
        f"- 状态：{'、'.join(status_flags)}",
    ]

    note = info.get("note")
    if note:
        lines.append(f"- 备注：{note}")
    last_used = _format_datetime(info.get("last_used_at"))
    lines.append(f"- 最近使用：{last_used}")

    return "\n".join(lines)


def refresh_activation_info(current_state: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not current_state or not current_state.get("code"):
        return None
    return ACTIVATION_MANAGER.get_code_info(current_state["code"])

def handle_activation_login(raw_code: str, current_state: Optional[Dict[str, Any]]):
    code = (raw_code or "").strip().upper()
    if not code:
        return (
            current_state,
            "⚠️ 请输入激活码。",
            gr.update(visible=True),
            gr.update(visible=False),
            False,
            format_activation_summary(current_state, False),
        )

    info = ACTIVATION_MANAGER.get_code_info(code)
    if not info:
        return (
            current_state,
            "❌ 激活码不存在，请确认后重试。",
            gr.update(visible=True),
            gr.update(visible=False),
            False,
            format_activation_summary(current_state, False),
        )
    if info.get("disabled"):
        return (
            current_state,
            "❌ 激活码已停用，请联系管理员。",
            gr.update(visible=True),
            gr.update(visible=False),
            False,
            format_activation_summary(current_state, False),
        )
    if info.get("expired"):
        return (
            current_state,
            "❌ 激活码已过期，请联系管理员。",
            gr.update(visible=True),
            gr.update(visible=False),
            False,
            format_activation_summary(current_state, False),
        )

    summary = format_activation_summary(info, False)
    return (
        info,
        "✅ 登录成功，欢迎使用阿左声音克隆产品 2.0。",
        gr.update(visible=False),
        gr.update(visible=True),
        False,
        summary,
    )


def handle_activation_logout(_: Optional[Dict[str, Any]]):
    summary = format_activation_summary(None, False)
    return (
        None,
        gr.update(visible=True),
        gr.update(visible=False),
        False,
        summary,
        "ℹ️ 已退出登录，请输入激活码继续使用。",
    )


def toggle_activation_reveal(reveal_full: bool, activation_state: Optional[Dict[str, Any]]):
    summary = format_activation_summary(activation_state, reveal_full)
    return summary, reveal_full


def handle_activation_refresh(
    activation_state: Optional[Dict[str, Any]],
    reveal_full: bool,
) -> Tuple[Optional[Dict[str, Any]], str]:
    fresh = refresh_activation_info(activation_state)
    if not fresh:
        return None, format_activation_summary(None, reveal_full)
    summary = format_activation_summary(fresh, reveal_full)
    return fresh, summary

def build_codes_table_rows() -> List[List[str]]:
    rows: List[List[str]] = []
    for info in ACTIVATION_MANAGER.list_codes():
        if info.get("max_voices", 0) == 0:
            voice_text = "无限"
        else:
            voice_text = f"{info.get('available_voices', 0)} / {info.get('max_voices', 0)}"
        if info.get("max_characters", 0) == 0:
            char_text = "无限"
        else:
            char_text = f"{info.get('remaining_characters', 0)} / {info.get('max_characters', 0)}"
        expires = info.get("expires_at") or "长期有效"
        status_flags: List[str] = []
        if info.get("disabled"):
            status_flags.append("停用")
        if info.get("expired"):
            status_flags.append("过期")
        if not status_flags:
            status_flags.append("正常")
        rows.append(
            [
                info.get("code", ""),
                voice_text,
                char_text,
                expires,
                "、".join(status_flags),
                info.get("note") or "-",
                _format_datetime(info.get("created_at")),
                _format_datetime(info.get("last_used_at")),
            ]
        )
    return rows


def handle_admin_login(password: str, current_state: bool):
    password = (password or "").strip()
    if not password:
        return current_state, "⚠️ 请输入后台口令。", gr.update()
    if password != config.get_admin_password():
        return False, "❌ 后台口令错误。", gr.update(visible=False)
    return True, "✅ 后台登录成功。", gr.update(visible=True)


def handle_admin_generate(
    admin_active: bool,
    voice_limit: Optional[float],
    char_limit: Optional[float],
    expires_at: str,
    note: str,
):
    if not admin_active:
        return "", "⚠️ 请先完成后台登录。", gr.update(value=build_codes_table_rows())
    try:
        voice_limit_int = int(voice_limit) if voice_limit is not None else 0
        char_limit_int = int(char_limit) if char_limit is not None else 0
        expires_str = (expires_at or "").strip() or None
        info = ACTIVATION_MANAGER.create_code(
            max_voices=max(voice_limit_int, 0),
            max_characters=max(char_limit_int, 0),
            expires_at=expires_str,
            note=note or "",
        )
    except (ActivationError, ValueError) as exc:
        return "", f"❌ 生成失败：{exc}", gr.update(value=build_codes_table_rows())
    rows = build_codes_table_rows()
    message = f"✅ 已生成激活码：{info['code']}"
    return info["code"], message, gr.update(value=rows)


def handle_admin_refresh(admin_active: bool):
    rows = build_codes_table_rows()
    if not admin_active:
        return gr.update(value=rows), "⚠️ 请先完成后台登录。"
    return gr.update(value=rows), "✅ 已刷新激活码列表。"


def handle_admin_update(
    admin_active: bool,
    code: str,
    voice_limit: Optional[float],
    char_limit: Optional[float],
    expires_at: str,
    note: str,
):
    rows = build_codes_table_rows()
    if not admin_active:
        return "⚠️ 请先完成后台登录。", gr.update(value=rows)
    code = (code or "").strip().upper()
    if not code:
        return "⚠️ 请填写要更新的激活码。", gr.update(value=rows)
    kwargs: Dict[str, Any] = {}
    if voice_limit is not None:
        kwargs["max_voices"] = max(int(voice_limit), 0)
    if char_limit is not None:
        kwargs["max_characters"] = max(int(char_limit), 0)
    if expires_at is not None:
        expires_str = expires_at.strip()
        kwargs["expires_at"] = expires_str or None
    if note is not None:
        kwargs["note"] = note
    try:
        ACTIVATION_MANAGER.update_code(code, **kwargs)
    except (ActivationError, ValueError) as exc:
        return f"❌ 更新失败：{exc}", gr.update(value=build_codes_table_rows())
    return f"✅ 激活码 {code} 已更新。", gr.update(value=build_codes_table_rows())


def handle_admin_toggle(admin_active: bool, code: str, disabled: bool):
    rows = build_codes_table_rows()
    if not admin_active:
        return "⚠️ 请先完成后台登录。", gr.update(value=rows)
    code = (code or "").strip().upper()
    if not code:
        return "⚠️ 请填写要操作的激活码。", gr.update(value=rows)
    try:
        ACTIVATION_MANAGER.update_code(code, disabled=disabled)
    except ActivationError as exc:
        return f"❌ 操作失败：{exc}", gr.update(value=build_codes_table_rows())
    state_text = "已禁用" if disabled else "已启用"
    return f"✅ 激活码 {code} {state_text}。", gr.update(value=build_codes_table_rows())

def voice_clone(
    reference_audio: Optional[str],
    text: str,
    use_saved_voice: bool,
    custom_voice_name: str,
    saved_voice_uri: str,
    speed: float,
    pitch: float,
    volume: float,
    response_format: str,
    do_sample: bool,
    temperature: float,
    top_p: float,
    top_k: float,
    repetition_penalty: float,
    length_penalty: float,
    num_beams: float,
    max_mel_tokens: float,
    emotion_mode: str,
    emotion_audio: Optional[str],
    emo_happy: float,
    emo_angry: float,
    emo_sad: float,
    emo_fear: float,
    emo_disgust: float,
    emo_melancholic: float,
    emo_surprise: float,
    emo_calm: float,
    emotion_text: str,
    emo_alpha: float,
    activation_state: Optional[Dict[str, Any]],
    reveal_full_code: bool,
) -> Tuple[Optional[str], str, str, str, Optional[Dict[str, Any]], str]:
    text = (text or "").strip()
    if not text:
        summary = format_activation_summary(activation_state, reveal_full_code)
        return None, "请输入要合成的文本。", saved_voice_uri, saved_voice_uri, activation_state, summary

    if not activation_state or not activation_state.get("code"):
        summary = format_activation_summary(activation_state, reveal_full_code)
        return None, "请先输入激活码完成登录。", saved_voice_uri, saved_voice_uri, activation_state, summary

    code = activation_state["code"]
    fresh_info = ACTIVATION_MANAGER.get_code_info(code)
    if not fresh_info:
        summary = format_activation_summary(None, reveal_full_code)
        return None, "激活码无效或已被移除，请重新登录。", saved_voice_uri, saved_voice_uri, None, summary
    if fresh_info.get("disabled") or fresh_info.get("expired"):
        summary = format_activation_summary(fresh_info, reveal_full_code)
        return None, "当前激活码不可用，请联系管理员。", saved_voice_uri, saved_voice_uri, fresh_info, summary

    saved_voice_uri = (saved_voice_uri or "").strip()
    use_saved_voice = bool(use_saved_voice)
    needs_new_voice = not (use_saved_voice and saved_voice_uri)
    characters_needed = len(text)

    ok, quota_message, quota_info = ACTIVATION_MANAGER.ensure_quota(code, characters_needed, needs_new_voice)
    if not ok:
        summary = format_activation_summary(quota_info or fresh_info, reveal_full_code)
        return None, quota_message, saved_voice_uri, saved_voice_uri, quota_info or fresh_info, summary

    activation_info = quota_info or fresh_info

    api_key = config.get_api_key()
    if not api_key:
        summary = format_activation_summary(activation_info, reveal_full_code)
        return None, "API 密钥未配置，请检查 siliconflowkey.env 文件。", saved_voice_uri, saved_voice_uri, activation_info, summary

    voice_uri = saved_voice_uri
    created_voice_uri: Optional[str] = None
    upload_message = ""

    if use_saved_voice and saved_voice_uri:
        upload_message = f"使用已有音色 URI：{voice_uri}"
    else:
        if not reference_audio:
            summary = format_activation_summary(activation_info, reveal_full_code)
            if use_saved_voice:
                return None, "未检测到已保存的音色 URI，请先上传参考音频。", saved_voice_uri, saved_voice_uri, activation_info, summary
            return None, "请上传参考音频。", saved_voice_uri, saved_voice_uri, activation_info, summary

        custom_name = _build_custom_name(custom_voice_name)
        voice_uri, error = _upload_reference_audio(
            audio_path=reference_audio,
            api_key=api_key,
            custom_name=custom_name,
            sample_text=text,
        )
        if error:
            summary = format_activation_summary(activation_info, reveal_full_code)
            return None, error, saved_voice_uri, saved_voice_uri, activation_info, summary
        created_voice_uri = voice_uri
        upload_message = f"已上传音色并获得 URI：{voice_uri}"

    payload = {
        "model": config.MODEL_NAME,
        "input": text,
        "voice": voice_uri,
        "response_format": response_format or "mp3",
        "speed": speed,
        "pitch": pitch,
        "volume": volume,
        "do_sample": bool(do_sample),
        "temperature": temperature,
        "top_p": top_p,
        "top_k": int(top_k),
        "repetition_penalty": repetition_penalty,
        "length_penalty": length_penalty,
        "num_beams": int(num_beams),
        "max_mel_tokens": int(max_mel_tokens),
        "emo_alpha": emo_alpha,
    }

    emotion_mode = (emotion_mode or EMOTION_MODE_OPTIONS[0]).strip()
    emotion_message = f"情感模式={emotion_mode}"

    if emotion_mode == EMOTION_MODE_OPTIONS[1]:
        if not emotion_audio:
            summary = format_activation_summary(activation_info, reveal_full_code)
            return None, "请上传情感参考音频。", saved_voice_uri, saved_voice_uri, activation_info, summary
        encoded_audio, error = _encode_audio_for_payload(emotion_audio, "情感参考音频")
        if error:
            summary = format_activation_summary(activation_info, reveal_full_code)
            return None, error, saved_voice_uri, saved_voice_uri, activation_info, summary
        payload["emotion_audio"] = encoded_audio
        emotion_message += "（参考上传的情感音频）"
    elif emotion_mode == EMOTION_MODE_OPTIONS[2]:
        emotion_vector = [
            float(emo_happy),
            float(emo_angry),
            float(emo_sad),
            float(emo_fear),
            float(emo_disgust),
            float(emo_melancholic),
            float(emo_surprise),
            float(emo_calm),
        ]
        if max(emotion_vector) <= 0:
            summary = format_activation_summary(activation_info, reveal_full_code)
            return None, "请调整情感向量（至少一个维度大于 0）。", saved_voice_uri, saved_voice_uri, activation_info, summary
        rounded_vector = [round(val, 4) for val in emotion_vector]
        payload["emotion_vector"] = rounded_vector
        pairs = ", ".join(f"{label}:{val:.2f}" for label, val in zip(EMOTION_VECTOR_LABELS, rounded_vector))
        emotion_message += f"（向量：{pairs}）"
    elif emotion_mode == EMOTION_MODE_OPTIONS[3]:
        emotion_text = (emotion_text or "").strip()
        if not emotion_text:
            summary = format_activation_summary(activation_info, reveal_full_code)
            return None, "请填写情感描述文本。", saved_voice_uri, saved_voice_uri, activation_info, summary
        payload["emotion_text"] = emotion_text
        emotion_message += f"（描述：{emotion_text}）"
    else:
        emotion_mode = EMOTION_MODE_OPTIONS[0]
        emotion_message = f"情感模式={emotion_mode}"

    audio_path, status = _call_siliconflow(payload)

    if audio_path:
        if created_voice_uri:
            status = f"声音克隆成功。\n{upload_message}"
        else:
            status = f"声音克隆成功（{upload_message}）。"
    else:
        status = f"{status}\n{upload_message}" if upload_message else status

    new_saved_uri = created_voice_uri or saved_voice_uri
    display_uri = created_voice_uri or saved_voice_uri or voice_uri or ""

    param_summary = (
        f"采样={'开' if do_sample else '关'}, temperature={temperature}, top_p={top_p}, top_k={int(top_k)}, "
        f"重复惩罚={repetition_penalty}, num_beams={int(num_beams)}, 最大Mel={int(max_mel_tokens)}, 情感强度={emo_alpha}"
    )
    param_summary += f"，{emotion_message}"

    if audio_path:
        try:
            activation_info = ACTIVATION_MANAGER.record_usage(
                code,
                characters_needed,
                created_voice_uri is not None,
            )
        except ActivationError as exc:
            status = f"{status}\n⚠️ 用量记录失败：{exc}"

    summary = format_activation_summary(activation_info, reveal_full_code)
    status = f"{status}\n{param_summary}"

    return audio_path, status, new_saved_uri, display_uri, activation_info, summary

def refresh_api_status() -> str:
    api_key = config.get_api_key()
    if not api_key:
        return "⚠ 未检测到 API 密钥，请在 siliconflowkey.env 中写入：API_KEY=你的密钥"

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(
            "https://api.siliconflow.cn/v1/models",
            headers=headers,
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        return f"❌ 无法连接硅基流动 API：{exc}"

    if response.status_code != 200:
        return (
            f"❌ 无法获取模型列表（HTTP {response.status_code}）："
            f"{response.text[:200]}"
        )

    try:
        data = response.json()
    except ValueError:
        return "⚠ 模型列表响应不是有效的 JSON。"

    model_ids = [item.get("id") for item in data.get("data", [])]
    key_preview = (
        f"{api_key[:4]}***{api_key[-4:]}" if len(api_key) >= 8 else "***"
    )

    if config.MODEL_NAME in model_ids:
        return f"✅ 密钥已加载（{key_preview}），模型 {config.MODEL_NAME} 可用。"

    if model_ids:
        return (
            f"⚠ 密钥已加载（{key_preview}），但模型列表未包含 {config.MODEL_NAME}。"
        )

    return f"⚠ 密钥已加载（{key_preview}），但未获取到任何模型数据。"


def build_client_app() -> gr.Blocks:
    with gr.Blocks(
        title="Ai Push Voice Clone 2.0",
        theme=gr.themes.Soft(),
        analytics_enabled=False,
        css=CUSTOM_CSS,
    ) as demo:
        activation_state = gr.State(None)
        reveal_state = gr.State(False)
        saved_voice_state = gr.State("")

        gr.Markdown(
            """\
# Ai Push Voice Clone 2.0

给你最好的声音克隆体验。
"""
        )

        with gr.Group(visible=True) as login_panel:
            gr.Markdown("请输入有效激活码以启用声音克隆服务。")
            activation_code_input = gr.Textbox(
                label="激活码",
                placeholder="请输入激活码",
                type="password",
            )
            login_button = gr.Button("登录", variant="primary")
            login_feedback = gr.Markdown()

        with gr.Column(visible=False) as main_panel:
            summary_display = gr.Markdown(format_activation_summary(None, False))
            with gr.Row():
                reveal_checkbox = gr.Checkbox(label="显示完整激活码", value=False)
                refresh_quota_button = gr.Button("刷新额度", variant="secondary")
                logout_button = gr.Button("退出登录", variant="secondary")
            with gr.Row():
                with gr.Column(scale=2):
                    clone_text = gr.Textbox(
                        label="合成文本",
                        placeholder="请输入要克隆的播报文本...",
                        lines=6,
                    )
                    clone_audio = gr.Audio(
                        label='参考音频（支持 mp3/wav/m4a/ogg/flac）',
                        type='filepath',
                        sources=['upload'],
                    )
                    clone_use_saved = gr.Checkbox(
                        label="复用最近生成的音色",
                        value=True,
                    )
                    clone_voice_name = gr.Textbox(
                        label="音色名称（可选）",
                        placeholder="用于标记本次音色，未填写时自动生成。",
                    )
                    with gr.Row():
                        clone_speed = gr.Slider(
                            label="语速",
                            minimum=0.5,
                            maximum=2.0,
                            step=0.05,
                            value=config.DEFAULT_SPEED,
                        )
                        clone_pitch = gr.Slider(
                            label="音调",
                            minimum=0.5,
                            maximum=2.0,
                            step=0.05,
                            value=config.DEFAULT_PITCH,
                        )
                        clone_volume = gr.Slider(
                            label="音量",
                            minimum=0.5,
                            maximum=2.0,
                            step=0.05,
                            value=config.DEFAULT_VOLUME,
                        )
                    clone_format = gr.Dropdown(
                        label="输出格式",
                        choices=config.SUPPORTED_AUDIO_FORMATS,
                        value='mp3',
                    )
                    clone_emotion_mode = gr.Radio(
                        label="情感控制方式",
                        choices=EMOTION_MODE_OPTIONS,
                        value=EMOTION_MODE_OPTIONS[0],
                        info="官方提供四种方式：跟随音色、情感参考音频、情感向量、情感描述文本。",
                    )
                    clone_emotion_audio = gr.Audio(
                        label="情感参考音频",
                        type='filepath',
                        sources=['upload'],
                        visible=False,
                    )
                    clone_emotion_vector_sliders: List[gr.Slider] = []
                    with gr.Row():
                        for label in EMOTION_VECTOR_LABELS[:4]:
                            slider = gr.Slider(
                                label=label,
                                minimum=0.0,
                                maximum=1.0,
                                step=0.05,
                                value=0.0,
                                visible=False,
                            )
                            clone_emotion_vector_sliders.append(slider)
                    with gr.Row():
                        for label in EMOTION_VECTOR_LABELS[4:]:
                            slider = gr.Slider(
                                label=label,
                                minimum=0.0,
                                maximum=1.0,
                                step=0.05,
                                value=0.0,
                                visible=False,
                            )
                            clone_emotion_vector_sliders.append(slider)
                    clone_emotion_text = gr.Textbox(
                        label="情感描述（可选）",
                        placeholder="示例：充满活力 / 沉稳 / 亲切...",
                        info="配合情感描述模式使用，引导语气情绪。",
                        visible=False,
                    )
                    clone_button = gr.Button("开始声音克隆", variant="primary")
                with gr.Column():
                    clone_output = gr.Audio(
                        label="克隆结果预览",
                        type='filepath',
                        autoplay=True,
                    )
                    clone_status = gr.Markdown("请上传参考音频并输入文本后开始。")
                    clone_voice_info = gr.Textbox(
                        label="最近生成的音色 URI",
                        value="",
                        interactive=False,
                        visible=False,
                    )
            with gr.Column(visible=False):
                clone_preset = gr.Radio(
                    label="参数预设",
                    choices=list(ADVANCED_PRESETS.keys()),
                    value=DEFAULT_PRESET,
                    visible=False,
                )
                clone_do_sample = gr.Checkbox(
                    label="启用采样（do_sample）",
                    value=True,
                    visible=False,
                )
                clone_temperature = gr.Slider(
                    label="温度 Temperature",
                    minimum=0.1,
                    maximum=1.5,
                    step=0.05,
                    value=0.72,
                    visible=False,
                )
                clone_top_p = gr.Slider(
                    label="Top-p",
                    minimum=0.1,
                    maximum=1.0,
                    step=0.05,
                    value=0.86,
                    visible=False,
                )
                clone_top_k = gr.Slider(
                    label="Top-k",
                    minimum=1,
                    maximum=100,
                    step=1,
                    value=40,
                    visible=False,
                )
                clone_repetition_penalty = gr.Slider(
                    label="重复惩罚（repetition_penalty）",
                    minimum=1.0,
                    maximum=15.0,
                    step=0.5,
                    value=9.0,
                    visible=False,
                )
                clone_length_penalty = gr.Slider(
                    label="长度惩罚（length_penalty）",
                    minimum=-2.0,
                    maximum=2.0,
                    step=0.1,
                    value=0.0,
                    visible=False,
                )
                clone_num_beams = gr.Slider(
                    label="Beam 数（num_beams）",
                    minimum=1,
                    maximum=5,
                    step=1,
                    value=4,
                    visible=False,
                )
                clone_max_mel_tokens = gr.Slider(
                    label="最大 Mel Tokens（max_mel_tokens）",
                    minimum=500,
                    maximum=3000,
                    step=50,
                    value=1600,
                    visible=False,
                )
                clone_emo_alpha = gr.Slider(
                    label="情感融合强度（emo_alpha）",
                    minimum=0.0,
                    maximum=1.0,
                    step=0.05,
                    value=0.9,
                    visible=False,
                )

        login_button.click(
            fn=handle_activation_login,
            inputs=[activation_code_input, activation_state],
            outputs=[
                activation_state,
                login_feedback,
                login_panel,
                main_panel,
                reveal_state,
                summary_display,
            ],
        )

        logout_button.click(
            fn=handle_activation_logout,
            inputs=[activation_state],
            outputs=[
                activation_state,
                login_panel,
                main_panel,
                reveal_state,
                summary_display,
                login_feedback,
            ],
        )

        reveal_checkbox.change(
            fn=toggle_activation_reveal,
            inputs=[reveal_checkbox, activation_state],
            outputs=[summary_display, reveal_state],
        )

        refresh_quota_button.click(
            fn=handle_activation_refresh,
            inputs=[activation_state, reveal_state],
            outputs=[activation_state, summary_display],
        )

        clone_preset.change(
            fn=apply_clone_preset_wrapper,
            inputs=clone_preset,
            outputs=[
                clone_emotion_mode,
                clone_do_sample,
                clone_temperature,
                clone_top_p,
                clone_top_k,
                clone_repetition_penalty,
                clone_length_penalty,
                clone_num_beams,
                clone_max_mel_tokens,
                clone_emotion_text,
                clone_emo_alpha,
            ],
        )

        clone_emotion_mode.change(
            fn=update_emotion_mode_controls,
            inputs=clone_emotion_mode,
            outputs=[
                clone_emotion_audio,
                *clone_emotion_vector_sliders,
                clone_emotion_text,
            ],
        )

        clone_button.click(
            fn=voice_clone,
            inputs=[
                clone_audio,
                clone_text,
                clone_use_saved,
                clone_voice_name,
                saved_voice_state,
                clone_speed,
                clone_pitch,
                clone_volume,
                clone_format,
                clone_do_sample,
                clone_temperature,
                clone_top_p,
                clone_top_k,
                clone_repetition_penalty,
                clone_length_penalty,
                clone_num_beams,
                clone_max_mel_tokens,
                clone_emotion_mode,
                clone_emotion_audio,
                *clone_emotion_vector_sliders,
                clone_emotion_text,
                clone_emo_alpha,
                activation_state,
                reveal_state,
            ],
            outputs=[
                clone_output,
                clone_status,
                saved_voice_state,
                clone_voice_info,
                activation_state,
                summary_display,
            ],
        )

    return demo


def build_admin_app() -> gr.Blocks:
    with gr.Blocks(
        title="阿左声音克隆管理后台",
        theme=gr.themes.Soft(),
        analytics_enabled=False,
        css=CUSTOM_CSS,
    ) as admin_demo:
        admin_logged_state = gr.State(False)
        disable_flag_state = gr.State(True)
        enable_flag_state = gr.State(False)

        gr.Markdown(
            """\
# 阿左声音克隆管理后台

用于生成、分发和维护激活码额度。
"""
        )

        admin_password = gr.Textbox(label="后台口令", type="password")
        admin_login_button = gr.Button("登录后台", variant="primary")
        admin_status = gr.Markdown()

        with gr.Group(visible=False) as admin_controls:
            with gr.Tabs():
                with gr.Tab("生成激活码"):
                    new_voice_limit = gr.Number(
                        label="可用音色数量（0 表示无限）",
                        value=5,
                        precision=0,
                    )
                    new_char_limit = gr.Number(
                        label="可用字符数量（0 表示无限）",
                        value=5000,
                        precision=0,
                    )
                    new_expiry = gr.Textbox(
                        label="有效期（YYYY-MM-DD，可留空）",
                        placeholder="例如：2025-12-31",
                    )
                    new_note = gr.Textbox(
                        label="备注（可选）",
                        placeholder="用于内部标记。",
                    )
                    generate_code_button = gr.Button("生成激活码", variant="primary")
                    generated_code_box = gr.Textbox(
                        label="最新生成的激活码",
                        interactive=False,
                    )
                with gr.Tab("激活码列表与维护"):
                    refresh_codes_button = gr.Button("刷新列表", variant="secondary")
                    codes_table = gr.DataFrame(
                        value=build_codes_table_rows(),
                        headers=[
                            "激活码",
                            "音色额度",
                            "字符额度",
                            "有效期",
                            "状态",
                            "备注",
                            "创建时间",
                            "最近使用",
                        ],
                        datatype=["str"] * 8,
                        interactive=False,
                        wrap=True,
                    )
                    update_code_input = gr.Textbox(
                        label="要更新的激活码",
                        placeholder="请输入完整激活码字符串",
                    )
                    update_voice_limit = gr.Number(
                        label="新的音色额度（留空不修改）",
                        precision=0,
                    )
                    update_char_limit = gr.Number(
                        label="新的字符额度（留空不修改）",
                        precision=0,
                    )
                    update_expiry = gr.Textbox(
                        label="新的有效期（YYYY-MM-DD，留空不修改，输入空格清除）",
                    )
                    update_note = gr.Textbox(
                        label="新的备注（留空不修改）",
                    )
                    update_code_button = gr.Button("更新激活码", variant="primary")
                    disable_code_button = gr.Button("禁用激活码", variant="stop")
                    enable_code_button = gr.Button("启用激活码", variant="secondary")

        admin_login_button.click(
            fn=handle_admin_login,
            inputs=[admin_password, admin_logged_state],
            outputs=[admin_logged_state, admin_status, admin_controls],
            queue=False,
        )

        generate_code_button.click(
            fn=handle_admin_generate,
            inputs=[
                admin_logged_state,
                new_voice_limit,
                new_char_limit,
                new_expiry,
                new_note,
            ],
            outputs=[
                generated_code_box,
                admin_status,
                codes_table,
            ],
            queue=False,
        )

        refresh_codes_button.click(
            fn=handle_admin_refresh,
            inputs=[admin_logged_state],
            outputs=[codes_table, admin_status],
            queue=False,
        )

        update_code_button.click(
            fn=handle_admin_update,
            inputs=[
                admin_logged_state,
                update_code_input,
                update_voice_limit,
                update_char_limit,
                update_expiry,
                update_note,
            ],
            outputs=[admin_status, codes_table],
            queue=False,
        )

        disable_code_button.click(
            fn=handle_admin_toggle,
            inputs=[admin_logged_state, update_code_input, disable_flag_state],
            outputs=[admin_status, codes_table],
            queue=False,
        )

        enable_code_button.click(
            fn=handle_admin_toggle,
            inputs=[admin_logged_state, update_code_input, enable_flag_state],
            outputs=[admin_status, codes_table],
            queue=False,
        )

    return admin_demo




def create_fastapi_app() -> FastAPI:
    main_app = FastAPI()

    client_blocks = build_client_app()
    admin_blocks = build_admin_app()

    admin_sub_app = FastAPI(root_path="/azttsdamin")
    admin_sub_app = gr.mount_gradio_app(admin_sub_app, admin_blocks, path="/", root_path="/azttsdamin")
    main_app.mount("/azttsdamin", admin_sub_app)


    main_app = gr.mount_gradio_app(main_app, client_blocks, path="/")

    @main_app.get("/manifest.json")
    async def frontend_manifest():
        return {
            "name": "阿左声音克隆产品 2.0",
            "short_name": "阿左声音克隆",
            "start_url": "/",
            "display": "standalone",
            "lang": "zh-CN",
            "background_color": "#ffffff",
            "theme_color": "#4f46e5",
            "icons": [],
        }

    @main_app.get("/azttsdamin/manifest.json")
    async def admin_manifest():
        return {
            "name": "阿左声音克隆管理后台",
            "short_name": "克隆后台",
            "start_url": "/azttsdamin/",
            "display": "standalone",
            "lang": "zh-CN",
            "background_color": "#ffffff",
            "theme_color": "#0f172a",
            "icons": [],
        }

    return main_app


fastapi_app = create_fastapi_app()

if __name__ == "__main__":
    import os
    print("正在启动阿左声音克隆产品 2.0...")
    print(f"[DEBUG] APP_HOST from os.getenv: {os.getenv('APP_HOST', 'NOT_SET')}")
    print(f"[DEBUG] APP_PORT from os.getenv: {os.getenv('APP_PORT', 'NOT_SET')}")
    print(f"[DEBUG] config.APP_HOST: {config.APP_HOST}")
    print(f"[DEBUG] config.APP_PORT: {config.APP_PORT}")
    status_message = refresh_api_status()
    print(status_message)
    print("用户访问入口：http://{0}:{1}/".format(config.APP_HOST, config.APP_PORT))
    print("后台管理入口：http://{0}:{1}/azttsdamin".format(config.APP_HOST, config.APP_PORT))

    uvicorn.run(
        fastapi_app,
        host=config.APP_HOST,
        port=config.APP_PORT,
        log_level="info",
    )
