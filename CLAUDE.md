# CLAUDE.md

#始终用中文回复

此文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指导。

## 项目概述

IndexTTS2 声音克隆网页 - 基于 Gradio 和 FastAPI 构建的网页应用，调用硅基流动 API 的 IndexTTS2 模型，实现文本转语音与声音克隆功能。

## 运行应用

### 启动应用
```bash
python app.py
```

应用将在 `http://127.0.0.1:7860/`（客户端界面）和 `http://127.0.0.1:7860/azttsdamin`（管理后台）启动。

### 测试 API 连通性
```bash
python test_api.py
```

### 安装依赖
```bash
pip install -r requirements.txt
```

## 架构说明

### 主要应用结构

**app.py** - 主应用文件，包含：
- 挂载 Gradio 界面的 FastAPI 应用
- 客户端界面（`build_client_app`）- 面向最终用户的声音克隆 UI
- 管理界面（`build_admin_app`）- 位于 `/azttsdamin` 的激活码管理后台
- 两个独立的 Gradio 块挂载在同一个 FastAPI 应用上，使用不同的根路径

**activation_manager.py** - 处理激活码生命周期：
- 使用加密安全的随机字符串生成激活码
- 配额管理（音色额度、字符限制）
- 过期追踪与验证
- 使用记录
- 以 JSON 格式存储（activation_codes.json）

**config.py** - 配置管理：
- 从 `siliconflowkey.env` 文件加载 API 密钥
- 硅基流动 API 端点配置
- 应用主机/端口设置
- 语速、音调、音量的默认参数

**infer_v2.py** - IndexTTS2 推理引擎（如果使用本地模型）：
- 完整的基于 PyTorch 的 TTS 推理管道
- 支持通过向量、文本或参考音频进行情感控制
- 参考音频缓存以提升性能
- 多段文本处理
- 支持 GPU/CPU/MPS 设备，可选 FP16

### 关键工作流程

**声音克隆流程：**
1. 用户使用激活码登录（通过 `ActivationManager` 验证）
2. 用户上传参考音频 → 上传至硅基流动 API → 获得 `speech:` URI
3. URI 缓存在会话状态中以便复用
4. 文本合成使用该 URI，应用参数（语速、音调、音量、情感控制）
5. 记录使用情况（消耗的字符数、创建新音色时的音色额度）

**激活码系统：**
- 激活码为 16 位字母数字字符串（大写字母 + 数字）
- 每个激活码具有：max_voices（最大音色数）、max_characters（最大字符数）、expires_at（过期时间）、disabled（禁用标志）
- `ensure_quota()` 在合成前检查可用额度
- `record_usage()` 在成功生成后更新计数器

**API 集成：**
- 文本转语音：`POST https://api.siliconflow.cn/v1/audio/speech`
- 音色上传：`POST https://api.siliconflow.cn/v1/uploads/audio/voice`
- 模型：`IndexTeam/IndexTTS-2`
- 通过 `siliconflowkey.env` 中的 Bearer token 进行授权

### 高级参数

应用支持两种参数预设：
- **魔搭示例**：temperature=0.72, top_p=0.86, top_k=40, num_beams=4
- **通用默认**：temperature=0.8, top_p=0.8, top_k=30, num_beams=3

情感控制模式：
1. 与音色参考音频相同
2. 使用情感参考音频（在 payload 中进行 base64 编码）
3. 使用情感向量（8 维：高兴、愤怒、悲伤、害怕、厌恶、忧郁、惊讶、平静）
4. 使用情感描述文本

## 配置文件

**siliconflowkey.env** - 必须包含：
```
API_KEY=你的硅基流动api密钥
ADMIN_PASSWORD=你的管理员密码
```

**activation_codes.json** - 自动生成的激活码存储（请勿手动编辑）

## 重要实现注意事项

- 主 FastAPI 应用使用 `gr.mount_gradio_app()` 挂载 Gradio 应用
- 管理界面使用 `root_path="/azttsdamin"` 以实现正确路由
- 参考音频大小限制为每个文件 10 MB
- 在 `infer_v2.py` 中实现了音频缓存，避免重复处理相同的参考音频
- 应用使用 Gradio 的 `State` 组件在会话间维护激活信息和音色 URI
- 所有激活码都被规范化为大写以保持一致性
- 请求超时设置为连接 10 秒、读取 120 秒

## 文件组织

- `app.py`、`app_simple.py`、`app_backup.py` - 各种应用版本
- `test_*.py` - 路由和 API 功能的测试脚本
- `*.bat` 文件 - Windows 下安装和运行的便捷脚本
- `setup_and_run.py` - 交互式设置脚本
- `models.json`、`model_full.json` - 模型配置数据
- `quick_start.txt`、`model_readme.md` - 文档文件