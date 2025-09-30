# Render PostgreSQL 数据库设置指南

## 为什么需要数据库？

Render 免费版使用临时文件系统，每次服务重启时所有文件都会丢失。使用 PostgreSQL 数据库可以**永久保存激活码**，无需每次手动配置环境变量。

## 优势

✅ **自动持久化** - 创建的激活码永久保存，重启后不丢失
✅ **零维护** - 无需手动导出/导入激活码
✅ **免费** - Render 提供免费 PostgreSQL 数据库（90 天有效期）
✅ **自动切换** - 应用会自动检测数据库，无数据库时降级到 JSON 文件

## 设置步骤

### 1. 创建 PostgreSQL 数据库

1. 登录 [Render Dashboard](https://dashboard.render.com/)
2. 点击顶部的 **New +** 按钮
3. 选择 **PostgreSQL**
4. 填写信息：
   - **Name**: `azvoiceclone-db`（或任意名称）
   - **Database**: `azvoiceclone`
   - **User**: `azvoiceclone_user`（自动生成）
   - **Region**: 选择与 Web Service 相同的区域
   - **PostgreSQL Version**: 16（默认）
   - **Plan**: **Free**（重要：选择免费计划）
5. 点击 **Create Database**

等待 2-3 分钟，数据库创建完成。

### 2. 获取数据库连接 URL

1. 在 Render Dashboard 中，点击刚创建的数据库
2. 找到 **Connections** 部分
3. 复制 **Internal Database URL**（格式类似：`postgres://user:password@dpg-xxx-a.oregon-postgres.render.com/dbname`）

⚠️ **重要**：使用 **Internal Database URL**，不是 External

### 3. 配置 Web Service 环境变量

1. 返回 Render Dashboard，选择 `azvoiceclone` Web Service
2. 点击左侧 **Environment** 标签
3. 点击 **Add Environment Variable**
4. 添加变量：
   - **Key**: `DATABASE_URL`
   - **Value**: 粘贴步骤 2 复制的 Internal Database URL
5. 点击 **Save Changes**

Render 会自动重新部署（约 3-5 分钟）。

### 4. 验证数据库连接

部署完成后，查看 Web Service 的日志（Logs 标签）：

✅ **成功**：看到 `[激活码管理] 检测到 DATABASE_URL，使用 PostgreSQL 持久化存储`
❌ **失败**：看到 `[激活码管理] 使用 JSON 文件存储（本地开发模式）`

如果失败，检查 DATABASE_URL 是否正确设置。

### 5. 创建激活码

1. 访问管理后台：https://vipvoice3.aipush.fun/azttsadmin/
2. 登录
3. 创建新激活码
4. 激活码会自动保存到 PostgreSQL 数据库

### 6. 测试持久化

1. 在 Render Dashboard 中，手动重启服务（Settings → Manual Deploy → Deploy latest commit）
2. 等待重启完成
3. 访问管理后台，激活码应该仍然存在

## 数据库免费计划限制

- **存储**: 1 GB
- **有效期**: 90 天（到期后需要删除并重新创建）
- **连接数**: 100 个并发连接
- **备份**: 7 天保留期

对于激活码存储，1 GB 足够存储数百万条激活码记录。

## 数据迁移

### 从 JSON 文件迁移到数据库

如果之前使用 JSON 文件存储激活码，需要手动迁移：

1. 在管理后台逐个重新创建激活码
2. 或者使用数据库管理工具直接导入

### 数据库到期怎么办？

90 天后数据库到期，需要：

1. 创建新的 PostgreSQL 数据库
2. 更新 Web Service 的 `DATABASE_URL` 环境变量
3. 在管理后台重新创建激活码

**建议**：定期导出激活码列表到本地备份。

## 本地开发

本地开发时，如果没有设置 `DATABASE_URL` 环境变量，应用会自动使用 JSON 文件存储（`activation_codes.json`），无需配置 PostgreSQL。

## 故障排查

### 问题：日志显示"使用 JSON 文件存储"

**原因**：DATABASE_URL 未设置或格式错误

**解决**：
1. 检查 Environment 标签中是否有 `DATABASE_URL` 变量
2. 确认 URL 格式正确：`postgres://user:password@host/database`
3. 确认使用的是 Internal URL，不是 External URL

### 问题：数据库连接超时

**原因**：Web Service 和数据库在不同区域

**解决**：
1. 确保 Web Service 和数据库在同一区域（如都在 Oregon）
2. 使用 Internal Database URL

### 问题：激活码创建后立即消失

**原因**：数据库事务未提交

**解决**：查看日志中的错误信息，可能是数据库权限问题

## 环境变量对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **PostgreSQL**（推荐） | 自动持久化，零维护 | 需要额外配置，90 天到期 |
| **环境变量** | 简单 | 每次创建激活码需手动更新 |
| **JSON 文件** | 本地开发方便 | Render 上重启丢失数据 |

## 总结

**生产环境（Render）**：使用 PostgreSQL
**本地开发**：自动使用 JSON 文件
**应急方案**：使用环境变量 `DEFAULT_ACTIVATION_CODES`