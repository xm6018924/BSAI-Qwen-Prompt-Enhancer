@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title BSAI 海报墙一键诊断自愈 (v1.04.0)

echo ============================================================
echo   BSAI Qwen Prompt Enhancer - 海报墙一键诊断自愈
echo   ERR_INVALID_RESPONSE 修复工具 (v1.04.0)
echo ============================================================
echo.

rem ---- 1. 探测 ComfyUI 端口（默认 8188，常见变体兜底）----
set FOUND_PORT=
for %%P in (8188 8189 8190 8187 8186 8000 8080 3000) do (
  for /f %%C in ('curl.exe -s -o nul -m 3 -w "%%{http_code}" http://127.0.0.1:%%P/ 2^>nul') do (
    if "%%C"=="200" set FOUND_PORT=%%P
  )
  if defined FOUND_PORT goto :port_found
)

if not defined FOUND_PORT (
  echo [1/3] 未探测到运行中的 ComfyUI（常见端口 8188/8189/8190/8000 均无响应）。
  echo       请先启动 ComfyUI 再运行本脚本。
  goto :proxy
)

:port_found
echo [1/3] 已探测到 ComfyUI 运行中 - 端口: %FOUND_PORT%
set WALL_URL=http://127.0.0.1:%FOUND_PORT%/bsai_templates_wall

rem ---- 2. 测试海报墙直达路由 ----
for /f %%C in ('curl.exe -s -o nul -m 5 -w "%%{http_code}" "%WALL_URL%" 2^>nul') do set WALL_CODE=%%C
if "%WALL_CODE%"=="200" (
  echo [2/3] 海报墙直达路由正常 (HTTP 200)，升级已生效。
  goto :proxy_check
)
echo [2/3] 直达路由返回 %WALL_CODE%（非 200）。
echo       可能原因：插件未加载成功 / ComfyUI 版本过旧 / 插件未更新到 v1.04.0。
echo       请确认：1) 插件目录已 git pull 到最新；2) 完全重启 ComfyUI 后再试。
goto :proxy

:proxy_check
rem ---- 3. 代理自愈：确保 localhost/127.0.0.1 不被系统代理劫持 ----
echo [3/3] 检查系统代理是否拦截本机地址...
set PROXY_ENABLE=
for /f "tokens=3" %%V in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable 2^>nul ^| findstr /i ProxyEnable') do set PROXY_ENABLE=%%V
if not "%PROXY_ENABLE%"=="0x1" (
  echo       系统代理未开启，无需处理。
  goto :launch
)
set OVERRIDE=
for /f "tokens=3*" %%V in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride 2^>nul ^| findstr /i ProxyOverride') do set OVERRIDE=%%W
echo       当前 ProxyOverride: %OVERRIDE%
echo %OVERRIDE% | findstr /i "127.0.0.1" >nul
if not errorlevel 1 (
  echo %OVERRIDE% | findstr /i "localhost" >nul
  if not errorlevel 1 (
    echo       本机地址已在例外列表，无需处理。
    goto :launch
  )
)
echo       检测到代理开启但 127.0.0.1/localhost 不在例外列表——这正是 ERR_INVALID_RESPONSE 的常见原因。
echo       正在自动添加本机地址到例外列表（原值已备份到同目录 fix_wall_proxy_backup.reg）...
reg export "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" "%~dp0fix_wall_proxy_backup.reg" /y >nul 2>nul
if "%OVERRIDE%"=="" (set NEW_OVERRIDE=localhost;127.0.0.1;<local>) else (set NEW_OVERRIDE=%OVERRIDE%;localhost;127.0.0.1;<local>)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "%NEW_OVERRIDE%" /f >nul
echo       已添加，新例外列表: %NEW_OVERRIDE%
echo       提示：改完代理后若仍打不开，请重启浏览器。

:launch
echo.
echo ============================================================
echo   修复完成。正在用默认浏览器打开海报墙...
echo   直达地址: %WALL_URL%
echo   若浏览器未自动打开，请手动复制上面的地址访问。
echo ============================================================
start "" "%WALL_URL%"
goto :end

:proxy
echo.
echo 提示：若您开启了系统代理/VPN，请确认 127.0.0.1、localhost 已加入
echo       代理例外（本脚本在探测到端口时会自动修复）。也可手动访问：
echo       http://127.0.0.1:8188/bsai_templates_wall

:end
echo.
pause
endlocal
