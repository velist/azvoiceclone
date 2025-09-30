# Render 部署指南

## 快速部署步骤

### 1. 推送代码到 GitHub（已完成）
仓库地址：https://github.com/velist/azvoiceclone

### 2. 登录 Render
访问：https://render.com
- 使用 GitHub 账号登录
- 授权 Render 访问您的 GitHub 仓库

### 3. 创建新服务
1. 点击 "New +" → 选择 "Web Service"
2. 连接 GitHub 仓库：`velist/azvoiceclone`
3. Render 会自动检测到 `render.yaml` 配置文件

### 4. 配置环境变量（重要！）
在 Render 控制台的 Environment 标签中添加：

```
API_KEY=你的硅基流动API密钥
ADMIN_PASSWORD=你的管理员密码（默认 admin123）
```

**注意**：不要将真实的 API 密钥推送到 GitHub！

### 5. 配置自定义域名
1. 部署成功后，在 Render 控制台找到 Settings → Custom Domain
2. 添加域名：`vipvoice3.aipush.fun`
3. Render 会提供 CNAME 记录，例如：
   ```
   vipvoice3.aipush.fun CNAME xxx.onrender.com
   ```
4. 到您的 DNS 提供商（如 Cloudflare）添加此 CNAME 记录
5. 等待 DNS 生效（通常 5-15 分钟）

### 6. 访问应用
- 前台：`https://vipvoice3.aipush.fun/`
- 后台：`https://vipvoice3.aipush.fun/azttsadmin/`

## 免费套餐限制
- 15 分钟无请求后自动休眠
- 休眠后首次访问需要 30-60 秒唤醒
- 每月 750 小时运行时间（足够单个应用全天运行）

## 注意事项
1. **环境变量**必须在 Render 控制台手动添加，不要写入代码
2. **管理后台路径**已更新为 `/azttsadmin/`（项目文档中为 `/azttsdamin/`，需要同步修改 app.py）
3. 首次部署约需 5-10 分钟
4. activation_codes.json 存储在临时文件系统，重启后会丢失（需要升级为持久化存储或数据库）

## 故障排查
- 部署失败：检查 Render 日志，确认依赖安装成功
- 502 错误：应用可能在休眠，等待 30-60 秒
- API 调用失败：确认环境变量 API_KEY 已正确设置