# IndexTTS2 声音克隆网页

基于 [Gradio](https://github.com/gradio-app/gradio) 框架构建的前端界面，调用硅基流动 API 的哔哩哔哩 IndexTTS2 模型，实现文本转语音与声音克隆功能。

## 功能特点
- **文本转语音**：输入任意文本并指定 IndexTTS2 的音色 ID，快速获得语音文件。
- **声音克隆**：上传样本音频后自动生成 `speech:` 开头的音色 URI，并在界面中保存显示，可一键复用。
- **参数控制**：支持语速 / 音调 / 音量 / 输出格式，以及 Temperature、Top-p、Top-k、Beam 数、情感描述等高级调参项。
- **API 状态检测**：界面内置检测按钮，可实时确认密钥与模型是否可用。

## 环境准备
- Windows / macOS / Linux
- Python 3.8 及以上版本（建议 3.10）
- 已申请的硅基流动 API Key

### 尚未安装 Python？
1. 访问 [python.org/downloads](https://www.python.org/downloads/) 下载 64 位安装包。
2. 安装时勾选 “Add Python to PATH（将 Python 加入环境变量）”。
3. 安装完成后重新打开命令行，执行 `python --version` 确认是否安装成功。

## 快速开始
```bash
# 1. 安装所需依赖
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. 启动 Gradio 网页
python app.py
```
启动成功后，浏览器会自动访问 `http://127.0.0.1:7860`。

## 关键文件
```
TTS/
├── app.py               # 主界面（文本转语音 + 声音克隆）
├── app_simple.py        # 复用主界面的精简启动脚本
├── config.py            # 常量与密钥加载工具
├── test_api.py          # 命令行连通性测试脚本
├── requirements.txt     # Python 依赖列表
├── siliconflowkey.env   # 保存 API_KEY=... 的密钥文件
└── *.bat / setup_and_run.py 等辅助启动脚本
```

## 界面使用指南

### 1. 文本转语音
1. 填写需要合成的文本。
2. 输入 **音色 ID**（需在硅基流动控制台或官方文档查询 IndexTTS2 支持的音色）。
3. 调整语速、音调、音量及输出格式（默认 MP3）。
4. 点击“生成语音”，稍候即可在右侧试听或下载文件。

> 如果返回 “Invalid voice”，说明音色 ID 不在官方列表内，请重新核对。

### 2. 声音克隆
1. 上传清晰的参考音频（5~20 秒人声，≤10 MB）。
2. 输入要合成的新文本，可选填“自定义音色名称”（用于在硅基流动控制台中保存记录，留空则自动生成）。
3. 调整语速、音调、音量及输出格式，点击“生成克隆语音”。
4. 首次上传成功后，状态栏会返回 `speech:` URI，同时界面右侧会自动显示并保存该 URI；勾选“复用最近生成的音色”即可直接再次合成，无需重复上传参考音频。

> “高级参数（可对齐魔搭示例）”折叠面板默认提供魔搭社区常用组合：Temperature 0.72、Top-p 0.86、Top-k 40、Beam 4、情感“充满活力”、情感强度 0.9。也可以根据实际需求微调温度、采样范围、最大 Mel Tokens、情感描述等参数，以匹配官方案例。

## CLI 检查工具
```bash
python test_api.py
```
脚本将：
- 校验密钥是否可读取；
- 输出当前账号可用的模型；
- 支持输入音色 ID 或 `speech:` URI 做一次命令行合成测试。

## 常见问题
- **提示找不到 Python**：请先完成“尚未安装 Python？”步骤，并重新打开命令行。
- **API 密钥未加载**：确认 `siliconflowkey.env` 内格式为 `API_KEY=你的密钥`，文件位于项目根目录。
- **语音生成失败 / 超时**：
  - 检查网络是否可访问 `https://api.siliconflow.cn`；
  - 缩短文本或参考音频长度后重试；
  - 确认账号额度足够。
- **音色 ID / URI 不清楚**：登录硅基流动控制台，查看 IndexTTS2 模型文档或体验页列出的音色信息。

欢迎在完成基础配置后根据需要扩展界面或集成流程。

## 更多参考资料
- [IndexTTS 官方中文文档（GitHub）](https://github.com/index-tts/index-tts/blob/main/docs/README_zh.md)
- [IndexTTS2 论文与示例](https://index-tts.github.io/index-tts2.github.io/)
- [ModelScope IndexTTS2 模型页](https://modelscope.cn/models/IndexTeam/IndexTTS-2)
