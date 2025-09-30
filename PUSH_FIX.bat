@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo 正在推送路由修复到 GitHub...
echo.
git push origin main
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ 推送成功！提交: 512f435
    echo.
    echo Render 会在 3-5 分钟内自动部署更新。
    echo.
    echo 部署完成后，请测试以下端点：
    echo   1. https://vipvoice3.aipush.fun/version
    echo   2. https://vipvoice3.aipush.fun/api/check_codes
    echo   3. https://vipvoice3.aipush.fun/azttsadmin/
    echo.
    echo 预期结果：
    echo   - /version 显示版本信息（commit: 512f435）
    echo   - /api/check_codes 显示激活码数量
    echo   - 管理后台登录后显示激活码列表
) else (
    echo.
    echo ✗ 推送失败，请检查网络连接后重试。
)
echo.
pause