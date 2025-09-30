# Render 环境变量配置指南

## 问题说明

Render 免费版使用临时文件系统，每次服务重启（休眠唤醒、重新部署）时，所有写入的文件都会丢失，包括 `activation_codes.json`。

这导致在管理后台创建的激活码在服务重启后失效。

## 解决方案

使用环境变量 `DEFAULT_ACTIVATION_CODES` 保存激活码数据，应用启动时自动加载。

## 配置步骤

### 1. 生成环境变量值

在本地运行：
```bash
python generate_env_codes.py
```

这会读取本地的 `activation_codes.json` 并生成压缩的 JSON 字符串。

### 2. 复制 JSON 字符串

从脚本输出中复制 JSON 字符串，格式如下：
```json
{"codes":{"激活码":{"code":"...","max_voices":5,...}}}
```

### 3. 在 Render 中设置环境变量

1. 登录 [Render Dashboard](https://dashboard.render.com/)
2. 选择 `azvoiceclone` 服务
3. 点击左侧的 **Environment** 标签
4. 点击 **Add Environment Variable**
5. 输入：
   - **Key**: `DEFAULT_ACTIVATION_CODES`
   - **Value**: 粘贴步骤 2 复制的 JSON 字符串
6. 点击 **Save Changes**

Render 会自动触发重新部署（约 3-5 分钟）。

### 4. 验证

部署完成后，访问：
```
https://vipvoice3.aipush.fun/api/check_codes
```

应该能看到激活码数量和列表。

## 现有环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `API_KEY` | 硅基流动 API 密钥 | ✓ |
| `ADMIN_PASSWORD` | 管理后台密码 | ✓ |
| `APP_HOST` | 监听地址（Render 自动设置为 0.0.0.0） | ✓ |
| `APP_PORT` | 监听端口（Render 自动设置为 10000） | ✓ |
| `DEFAULT_ACTIVATION_CODES` | 默认激活码（JSON 格式） | 推荐 |

## 注意事项

1. **JSON 格式必须正确**
   - 确保没有多余的空格或换行
   - 确保所有引号和括号匹配

2. **更新激活码**
   - 在管理后台创建新激活码后，需要重新运行 `generate_env_codes.py`
   - 更新 Render 的 `DEFAULT_ACTIVATION_CODES` 环境变量

3. **安全性**
   - 不要将激活码数据提交到 Git 仓库
   - 仅通过 Render 的环境变量管理激活码

4. **数据同步**
   - 服务运行期间创建的激活码会保存在临时文件系统中
   - 重启后会恢复到 `DEFAULT_ACTIVATION_CODES` 中的状态
   - 建议定期导出重要的激活码到环境变量

## 长期解决方案

对于生产环境，建议使用持久化存储：
- PostgreSQL 数据库（Render 提供免费 PostgreSQL）
- Redis（用于缓存）
- 云存储服务（S3、阿里云 OSS 等）

当前的环境变量方案适合测试和小规模使用。