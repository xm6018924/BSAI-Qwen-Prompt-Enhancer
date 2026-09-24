@echo off
chcp 65001 >nul
REM =====================================================================
REM  BSAI Qwen Prompt Enhancer — 示例工作流依赖一键安装
REM  One-click install of dependency nodes for BSAI example workflows
REM  (潜空间放大示例 / 全功能多合一示例)
REM  用法: 双击运行; 装完必须【完全重启 ComfyUI】
REM =====================================================================
setlocal

set "PLUG_ROOT=%~dp0"
set "CN=%PLUG_ROOT%..\..\custom_nodes"

echo [1/4] 定位 custom_nodes 目录: %CN%
if not exist "%CN%" (
  echo [错误/ERROR] 未找到 custom_nodes 目录。请把本 bat 放在
  echo            ComfyUI/custom_nodes/BSAI_Qwen_Prompt_Enhancer/ 下运行。
  pause
  exit /b 1
)

echo [2/4] 检查并安装依赖插件 (git clone)...

set "NEED_CLONE="

if exist "%CN%\rgthree-comfy\__init__.py" (
  echo   [已有] rgthree-comfy          (Image Comparer ^(rgthree^))
) else (
  echo   [安装] rgthree-comfy          (Image Comparer ^(rgthree^))
  git clone --depth 1 https://github.com/rgthree/rgthree-comfy "%CN%\rgthree-comfy"
)

if exist "%CN%\ComfyUI-Qwen-Image-2.1-Prompt-Enhancer\__init__.py" (
  echo   [已有] ComfyUI-Qwen-Image-2.1-Prompt-Enhancer  (QwenImage21_T2IPromptRewrite)
) else (
  echo   [安装] ComfyUI-Qwen-Image-2.1-Prompt-Enhancer  (QwenImage21_T2IPromptRewrite)
  git clone --depth 1 https://github.com/benjiyaya/ComfyUI-Qwen-Image-2.1-Prompt-Enhancer "%CN%\ComfyUI-Qwen-Image-2.1-Prompt-Enhancer"
)

if exist "%CN%\ComfyUI-DLSS5-Enhancer\__init__.py" (
  echo   [已有] ComfyUI-DLSS5-Enhancer  (DLSS5Settings / DLSS5EnhanceImages)
) else (
  echo   [安装] ComfyUI-DLSS5-Enhancer  (DLSS5Settings / DLSS5EnhanceImages)
  git clone --depth 1 https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer "%CN%\ComfyUI-DLSS5-Enhancer"
)

if exist "%CN%\ComfyUI-KJNodes\__init__.py" (
  echo   [已有] ComfyUI-KJNodes         (SetNode/GetNode/PathchSageAttentionKJ/GetImageSizeAndCount)
) else (
  echo   [安装] ComfyUI-KJNodes         (SetNode/GetNode/PathchSageAttentionKJ/GetImageSizeAndCount)
  git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes "%CN%\ComfyUI-KJNodes"
)

if exist "%CN%\comfyui-easy-use\__init__.py" (
  echo   [已有] comfyui-easy-use        (easy cleanGpuUsed / easy clearCacheAll)
) else (
  echo   [安装] comfyui-easy-use        (easy cleanGpuUsed / easy clearCacheAll)
  git clone --depth 1 https://github.com/yolain/ComfyUI-Easy-Use "%CN%\comfyui-easy-use"
)

echo [3/4] DLSS5 潜空间放大运行时 (可选, 需 NVIDIA RTX) ...
if exist "%CN%\ComfyUI-DLSS5-Enhancer\install_runtime.py" (
  echo   DLSS5EnhanceImages 节点需要 DLSS5 运行时。按需运行下面命令:
  echo   python "%CN%\ComfyUI-DLSS5-Enhancer\install_runtime.py" --url "https://github.com/Merserk/dlss5-visual-enhancer/releases/download/v3.0/DLSS.5.Visual.Enhancer.v3.0.zip"
  echo   (注意: URL 必须带 tag 前缀 v3.0; 国内 GitHub 不通时在 URL 前加镜像前缀
  echo     https://gh-proxy.com/ 或 https://ghfast.top/ 再运行)
  echo   跳过不影响其它节点
)

echo [4/4] 完成!
echo  1) 请【完全重启 ComfyUI】(不是刷新页面)
echo  2) 示例工作流位置: custom_nodes/BSAI_Qwen_Prompt_Enhancer/examples/
echo     - BSAI-QwenImg_2-1_t2i-upscale.json          (Qwen-Image-2.1 潜空间放大)
echo     - BSAI-Qwen-Image-2.1-全功能多合一示例工作流.json
echo  3) 启动日志第一屏见 "[BSAI_Qwen_Prompt_Enhancer] 插件已加载 | 版本 v1.02" 即成功
pause
