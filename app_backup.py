import base64
import datetime
import mimetypes
import os
import tempfile
from typing import Optional, Tuple

import gradio as gr
import requests

import config

REQUEST_TIMEOUT = (10, 120)
MAX_REFERENCE_FILE_SIZE_MB = 10

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


def _advanced_preset_values(preset_name: str):
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
    ) = apply_advanced_preset(preset_name)

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


def _save_audio(content: bytes, response_format: str) -> str:
    suffix = f".{response_format.lower()}" if response_format else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(content)
        return tmp_file.name


def _call_siliconflow(payload: dict) -> Tuple[Optional[str], str]:
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
        return None, f"网络请求失败：{exc}"

    if response.status_code == 200:
        file_path = _save_audio(response.content, response_format)
        print(
            "[SiliconFlow] 请求成功",
            f"模型={payload.get('model')}",
            f"音频字节数={len(response.content)}",
        )
        return file_path, "语音生成成功。"

    try:
        error_detail = response.json()
    except ValueError:
        error_detail = response.text[:500]

    print(
        "[SiliconFlow] 请求失败",
        f"状态码={response.status_code}",
        f"详情={error_detail}",
    )
    return None, f"调用失败（HTTP {response.status_code}）：{error_detail}"


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
) -> Tuple[Optional[str], str, str, str]:
    text = (text or "").strip()
    if not text:
        return None, "请输入要合成的文本。", saved_voice_uri, saved_voice_uri

    api_key = config.get_api_key()
    if not api_key:
        return None, "API 密钥未配置，请检查 siliconflowkey.env 文件。", saved_voice_uri, saved_voice_uri

    saved_voice_uri = (saved_voice_uri or "").strip()
    voice_uri = saved_voice_uri
    use_saved_voice = bool(use_saved_voice)
    created_voice_uri: Optional[str] = None

    if use_saved_voice and saved_voice_uri:
        upload_message = f"使用已有音色 URI：{voice_uri}"
    else:
        if not reference_audio:
            if use_saved_voice:
                return (
                    None,
                    "未检测到已保存的音色 URI，请先上传参考音频。",
                    saved_voice_uri,
                    saved_voice_uri,
                )
            return None, "请上传参考音频。", saved_voice_uri, saved_voice_uri

        custom_name = _build_custom_name(custom_voice_name)
        voice_uri, error = _upload_reference_audio(
            audio_path=reference_audio,
            api_key=api_key,
            custom_name=custom_name,
            sample_text=text,
        )
        if error:
            return None, error, saved_voice_uri, saved_voice_uri
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
            return None, "请上传情感参考音频。", saved_voice_uri, saved_voice_uri
        encoded_audio, error = _encode_audio_for_payload(emotion_audio, "情感参考音频")
        if error:
            return None, error, saved_voice_uri, saved_voice_uri
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
            return None, "请调整情感向量（至少一个维度大于 0）。", saved_voice_uri, saved_voice_uri
        rounded_vector = [round(val, 4) for val in emotion_vector]
        payload["emotion_vector"] = rounded_vector
        pairs = ", ".join(f"{label}:{val:.2f}" for label, val in zip(EMOTION_VECTOR_LABELS, rounded_vector))
        emotion_message += f"（向量：{pairs}）"
    elif emotion_mode == EMOTION_MODE_OPTIONS[3]:
        emotion_text = (emotion_text or "").strip()
        if not emotion_text:
            return None, "请填写情感描述文本。", saved_voice_uri, saved_voice_uri
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

    status = f"{status}\n{param_summary}"

    return audio_path, status, new_saved_uri, display_uri

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


def apply_clone_preset_wrapper(preset_name: str):
    return apply_clone_preset(preset_name)


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="IndexTTS2 声音克隆工具", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            """
            # 🎧 IndexTTS2 声音克隆面板

            依托硅基流动 API 调用哔哩哔哩 IndexTTS2 模型，提供文本转语音与声音克隆的网页体验。
            """
        )

        with gr.Row():
            status_box = gr.Textbox(
                label="API 状态",
                value="正在检测 API...",
                interactive=False,
                lines=3,
            )
            refresh_button = gr.Button("重新检测 API")

        refresh_button.click(fn=refresh_api_status, outputs=status_box)
        demo.load(fn=refresh_api_status, outputs=status_box)

        with gr.Tab("文本转语音"):
            with gr.Row():
                with gr.Column(scale=2):
                    tts_text = gr.Textbox(
                        label="输入文本",
                        placeholder="请输入需要转换的文本...",
                        lines=6,
                    )
                    tts_voice = gr.Textbox(
                        label="音色 ID",
                        placeholder="请填写硅基流动提供的 IndexTTS2 音色 ID",
                    )
                    with gr.Row():
                        tts_speed = gr.Slider(
                            label="语速",
                            minimum=0.5,
                            maximum=2.0,
                            step=0.05,
                            value=config.DEFAULT_SPEED,
                        )
                        tts_pitch = gr.Slider(
                            label="音调",
                            minimum=0.5,
                            maximum=2.0,
                            step=0.05,
                            value=config.DEFAULT_PITCH,
                        )
                        tts_volume = gr.Slider(
                            label="音量",
                            minimum=0.5,
                            maximum=2.0,
                            step=0.05,
                            value=config.DEFAULT_VOLUME,
                        )
                    tts_format = gr.Dropdown(
                        label="输出格式",
                        choices=config.SUPPORTED_AUDIO_FORMATS,
                        value="mp3",
                    )
                    with gr.Accordion("高级参数（可对齐魔搭示例）", open=False):
                        tts_preset = gr.Radio(
                            label="参数预设",
                            choices=list(ADVANCED_PRESETS.keys()),
                            value=DEFAULT_PRESET,
                            info="一键套用魔搭示例或通用默认参数，可在下方微调",
                        )
                        tts_do_sample = gr.Checkbox(
                            label="启用采样（do_sample）",
                            value=True,
                            info="关闭后使用贪心解码，语气更稳定但较平淡",
                        )
                        with gr.Row():
                            tts_temperature = gr.Slider(
                                label="温度 Temperature",
                                minimum=0.1,
                                maximum=1.5,
                                step=0.05,
                                value=0.8,
                                info="数值越高越活泼，越低越平稳",
                            )
                            tts_top_p = gr.Slider(
                                label="Top-p",
                                minimum=0.1,
                                maximum=1.0,
                                step=0.05,
                                value=0.8,
                                info="控制采样概率质量，与温度搭配调整",
                            )
                            tts_top_k = gr.Slider(
                                label="Top-k",
                                minimum=1,
                                maximum=100,
                                step=1,
                                value=30,
                                info="采样候选数，越大越具多样性",
                            )
                        with gr.Row():
                            tts_repetition_penalty = gr.Slider(
                                label="重复惩罚（repetition_penalty）",
                                minimum=1.0,
                                maximum=15.0,
                                step=0.5,
                                value=10.0,
                                info="抑制重复字词，建议保持在 8~12",
                            )
                            tts_length_penalty = gr.Slider(
                                label="长度惩罚（length_penalty）",
                                minimum=-2.0,
                                maximum=2.0,
                                step=0.1,
                                value=0.0,
                                info="调节输出长度偏好，通常保持 0",
                            )
                            tts_num_beams = gr.Slider(
                                label="Beam 数（num_beams）",
                                minimum=1,
                                maximum=5,
                                step=1,
                                value=3,
                                info="越大越细致但推理更慢",
                            )
                        with gr.Row():
                            tts_max_mel_tokens = gr.Slider(
                                label="最大 Mel Tokens（max_mel_tokens）",
                                minimum=500,
                                maximum=3000,
                                step=50,
                                value=1500,
                                info="控制最长时长，文本较长时可适当调大",
                            )
                            tts_emo_alpha = gr.Slider(
                                label="情感融合强度（emo_alpha）",
                                minimum=0.0,
                                maximum=1.0,
                                step=0.05,
                                value=1.0,
                                info="0 表示无情感，1 表示完全按描述执行",
                            )
                        tts_emotion_text = gr.Textbox(
                            label="情感描述（可选）",
                            placeholder="示例：充满活力 / 温柔 / 沉稳...",
                            info="传递给 IndexTTS2 的 emotion_text，用于指导情感",
                        )
                        gr.Markdown(
                            "官方建议参数可参考 [IndexTTS 文档](https://github.com/index-tts/index-tts/blob/main/docs/README_zh.md)，魔搭示例常用组合：Temperature 0.72、Top-p 0.86、Top-k 40、Beam 4、情感“充满活力”、情感强度 0.9。",
                        )
                    tts_preset.change(
                        fn=apply_advanced_preset,
                        inputs=tts_preset,
                        outputs=[
                            tts_do_sample,
                            tts_temperature,
                            tts_top_p,
                            tts_top_k,
                            tts_repetition_penalty,
                            tts_length_penalty,
                            tts_num_beams,
                            tts_max_mel_tokens,
                            tts_emotion_text,
                            tts_emo_alpha,
                        ],
                    )
                    tts_button = gr.Button("生成语音", variant="primary")

                with gr.Column():
                    tts_audio = gr.Audio(
                        label="生成的音频",
                        type="filepath",
                        autoplay=True,
                    )
                    tts_status = gr.Textbox(
                        label="状态消息",
                        interactive=False,
                        lines=4,
                    )

            tts_button.click(
                fn=text_to_speech,
                inputs=[
                    tts_text,
                    tts_voice,
                    tts_speed,
                    tts_pitch,
                    tts_volume,
                    tts_format,
                    tts_do_sample,
                    tts_temperature,
                    tts_top_p,
                    tts_top_k,
                    tts_repetition_penalty,
                    tts_length_penalty,
                    tts_num_beams,
                    tts_max_mel_tokens,
                    tts_emotion_text,
                    tts_emo_alpha,
                ],
                outputs=[tts_audio, tts_status],
            )

        saved_voice_state = gr.State("")

        with gr.Tab("声音克隆"):
            with gr.Row():
                with gr.Column(scale=2):
                    clone_audio = gr.Audio(
                        label="上传参考音频",
                        type="filepath",
                        sources=["upload", "microphone"],
                    )
                    clone_text = gr.Textbox(
                        label="要合成的文本",
                        placeholder="请输入希望克隆声音朗读的文本...",
                        lines=6,
                    )
                    clone_use_saved = gr.Checkbox(
                        label="复用最近生成的音色（无需重新上传参考音频）",
                        value=False,
                    )
                    clone_voice_name = gr.Textbox(
                        label="自定义音色名称（可选）",
                        placeholder="用于在硅基流动控制台标识音色，留空则自动生成",
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
                        value="mp3",
                    )

                    clone_emotion_vector_sliders = []
                    with gr.Accordion("高级参数（可对齐魔搭示例）", open=False):
                        clone_preset = gr.Radio(
                            label="参数预设",
                            choices=list(ADVANCED_PRESETS.keys()),
                            value=DEFAULT_PRESET,
                            info="与文本转语音相同，一键套用魔搭示例或通用默认配置",
                        )
                        clone_do_sample = gr.Checkbox(
                            label="启用采样（do_sample）",
                            value=True,
                            info="关闭可获得更稳的语气，开启更具表现力",
                        )
                        with gr.Row():
                            clone_temperature = gr.Slider(
                                label="温度 Temperature",
                                minimum=0.1,
                                maximum=1.5,
                                step=0.05,
                                value=0.8,
                                info="建议配合 Top-p、Top-k 共同调整",
                            )
                            clone_top_p = gr.Slider(
                                label="Top-p",
                                minimum=0.1,
                                maximum=1.0,
                                step=0.05,
                                value=0.8,
                                info="累积概率阈值，控制采样范围",
                            )
                            clone_top_k = gr.Slider(
                                label="Top-k",
                                minimum=1,
                                maximum=100,
                                step=1,
                                value=30,
                                info="候选 token 数，越大越多样",
                            )
                        with gr.Row():
                            clone_repetition_penalty = gr.Slider(
                                label="重复惩罚（repetition_penalty）",
                                minimum=1.0,
                                maximum=15.0,
                                step=0.5,
                                value=10.0,
                                info="较高的惩罚能减少重复字词",
                            )
                            clone_length_penalty = gr.Slider(
                                label="长度惩罚（length_penalty）",
                                minimum=-2.0,
                                maximum=2.0,
                                step=0.1,
                                value=0.0,
                                info="调节时长倾向，通常保持 0",
                            )
                            clone_num_beams = gr.Slider(
                                label="Beam 数（num_beams）",
                                minimum=1,
                                maximum=5,
                                step=1,
                                value=3,
                                info="值越大越细致，耗时也会增加",
                            )
                        with gr.Row():
                            clone_max_mel_tokens = gr.Slider(
                                label="最大 Mel Tokens（max_mel_tokens）",
                                minimum=500,
                                maximum=3000,
                                step=50,
                                value=1500,
                                info="可理解为最长合成帧数，长文本可调高",
                            )
                            clone_emo_alpha = gr.Slider(
                                label="情感融合强度（emo_alpha）",
                                minimum=0.0,
                                maximum=1.0,
                                step=0.05,
                                value=1.0,
                                info="控制情感描述对最终音色的影响权重",
                            )
                        clone_emotion_mode = gr.Radio(
                            label="情感控制方式",
                            choices=EMOTION_MODE_OPTIONS,
                            value=EMOTION_MODE_OPTIONS[0],
                            info="官方提供四种方式：跟随音色、情感参考音频、情感向量、情感描述文本。",
                        )
                        clone_emotion_audio = gr.Audio(
                            label="情感参考音频",
                            type="filepath",
                            sources=["upload"],
                            visible=False,
                        )
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
                            info="配合情感描述模式使用，引导语气情绪",
                            visible=False,
                        )
                        gr.Markdown(
                            "魔搭示例常用组合：Temperature 0.72、Top-p 0.86、Top-k 40、Beam 4、情感“充满活力”、情感强度 0.9。",
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
                    clone_button = gr.Button("生成克隆语音", variant="primary")

                with gr.Column():
                    clone_output = gr.Audio(
                        label="克隆后的音频",
                        type="filepath",
                        autoplay=True,
                    )
                    clone_status = gr.Textbox(
                        label="状态消息",
                        interactive=False,
                        lines=4,
                    )
                    clone_voice_info = gr.Textbox(
                        label="最近生成的音色 URI",
                        value="",
                        placeholder="上传参考音频后自动生成",
                        info="复制此 URI 可在后续推理或 API 调用中直接复用",
                        interactive=False,
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
                ],
                outputs=[clone_output, clone_status, saved_voice_state, clone_voice_info],
            )

        with gr.Accordion("使用提示", open=False):
            gr.Markdown(
                """
                ### 获取音色 ID
                - 登录硅基流动平台，查阅 IndexTTS2 模型文档或控制台列出的音色标识。
                - 文本转语音需填写音色 ID；声音克隆可填写已有 `speech:` URI，或通过本页上传参考音频自动生成。

                ### 参考音频建议
                - 建议使用 5~20 秒的清晰人声，文件大小不超过 10 MB。
                - 支持 MP3、WAV、M4A、OGG、FLAC 等常见格式。

                ### 情感控制说明
                - **与音色参考音频相同**：默认模式，直接复用上传的音色音频情感。
                - **使用情感参考音频**：额外上传一段情感参考音频，用于指导情绪。
                - **使用情感向量控制**：分别调节高兴、愤怒、悲伤等 8 个维度（0~1）。
                - **使用情感描述文本控制**：通过文字（如“充满活力”）引导情绪，可配合魔搭示例。

                ### 常见排查步骤
                - 如果提示密钥未配置，请在 `siliconflowkey.env` 中写入：`API_KEY=你的密钥`。
                - 如果返回 “Invalid voice”，请确认 `voice` 参数为有效的音色 ID 或成功返回的 `speech:` URI。
                - 首次克隆成功后可复制“最近生成的音色 URI”，勾选“复用最近生成的音色”即可跳过再次上传。
                - 若请求频繁超时，可以适当缩短文本或稍后再试。
                """
            )

    return demo


demo = build_demo()


if __name__ == "__main__":
    print("正在启动 IndexTTS2 声音克隆网页...")
    status_message = refresh_api_status()
    print(status_message)

    demo.launch(
        server_name=config.APP_HOST,
        server_port=config.APP_PORT,
        share=config.APP_SHARE,
        inbrowser=True,
    )
