param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$runtimeRoot = Join-Path $ProjectRoot "data\runtimes\indextts2"
$paths = @{
    UV_PROJECT_ENVIRONMENT = Join-Path $runtimeRoot ".venv"
    UV_CACHE_DIR = Join-Path $runtimeRoot "uv-cache"
    UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot "uv-python"
    UV_PYTHON_CACHE_DIR = Join-Path $runtimeRoot "uv-python-cache"
    UV_TOOL_DIR = Join-Path $runtimeRoot "uv-tools"
    UV_TOOL_BIN_DIR = Join-Path $runtimeRoot "uv-tool-bin"
    HF_HOME = Join-Path $runtimeRoot "hf-home"
    HF_HUB_CACHE = Join-Path $runtimeRoot "hf-home\hub"
    HF_XET_CACHE = Join-Path $runtimeRoot "hf-home\xet"
    TORCH_EXTENSIONS_DIR = Join-Path $runtimeRoot "torch-extensions"
    XDG_CACHE_HOME = Join-Path $runtimeRoot "xdg-cache"
}

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
foreach ($path in $paths.Values) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

foreach ($entry in $paths.GetEnumerator()) {
    Set-Item -Path "Env:\$($entry.Key)" -Value $entry.Value
}

Write-Host "IndexTTS2 runtime paths are prepared under:"
Write-Host "  $runtimeRoot"
Write-Host ""
Write-Host "This script does not download dependencies or checkpoints."
Write-Host "Expected runtime python:"
Write-Host "  $($paths.UV_PROJECT_ENVIRONMENT)\Scripts\python.exe"
Write-Host "Expected checkpoints:"
Write-Host "  $(Join-Path $ProjectRoot 'third_party\index-tts\checkpoints\config.yaml')"
Write-Host "  $(Join-Path $ProjectRoot 'third_party\index-tts\checkpoints\bpe.model')"
Write-Host "  $(Join-Path $ProjectRoot 'third_party\index-tts\checkpoints\gpt.pth')"
Write-Host "  $(Join-Path $ProjectRoot 'third_party\index-tts\checkpoints\s2mel.pth')"
