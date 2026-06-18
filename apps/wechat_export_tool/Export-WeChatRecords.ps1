[CmdletBinding()]
param(
    [string]$DbDir = "",
    [string]$OutputRoot = "",
    [string]$SelfWxid = "",
    [string]$TargetChat = "",
    [switch]$SearchAllDrives,
    [switch]$SkipInstall,
    [switch]$SkipKeyScan,
    [switch]$CleanSensitive,
    [switch]$KeepSensitive
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutputRoot) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputRoot = Join-Path $ToolRoot "runs\$stamp"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-Python {
    $venvPython = Join-Path $ToolRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "python was not found. Install Python or add python to PATH."
    }
    Write-Step "Create tool Python virtualenv"
    & $pythonCmd.Source -m venv (Join-Path $ToolRoot ".venv")
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Failed to create virtualenv: $venvPython"
    }
    return $venvPython
}

function Ensure-PythonDeps {
    param([string]$Python)
    Write-Step "Install/check Python dependencies"
    & $Python -m pip install --upgrade pip | Out-Host
    & $Python -m pip install pycryptodome zstandard | Out-Host
}

function Ensure-WxCli {
    $wxCmd = Join-Path $ToolRoot "tools\wx-cli-npm\node_modules\.bin\wx.cmd"
    if (Test-Path -LiteralPath $wxCmd) {
        return $wxCmd
    }
    if ($SkipInstall) {
        throw "wx-cli is not installed and -SkipInstall was set. Missing: $wxCmd"
    }
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        throw "npm was not found. Install Node.js/npm or install @jackwener/wx-cli manually."
    }
    Write-Step "Install wx-cli package"
    $npmRoot = Join-Path $ToolRoot "tools\wx-cli-npm"
    New-Item -ItemType Directory -Force -Path $npmRoot | Out-Null
    & $npmCmd.Source install "@jackwener/wx-cli" --prefix $npmRoot | Out-Host
    if (-not (Test-Path -LiteralPath $wxCmd)) {
        throw "wx-cli entry was not found after install: $wxCmd"
    }
    return $wxCmd
}

function Find-DbDir {
    param([string]$Python)
    Write-Step "Locate WeChat db_storage"
    $args = @((Join-Path $ToolRoot "locate_wechat_db.py"))
    if ($DbDir) {
        $args += @("--db-dir", $DbDir)
    }
    if ($SearchAllDrives) {
        $args += "--search-all-drives"
    }
    $raw = & $Python @args
    $data = $raw | ConvertFrom-Json
    if (-not $data.candidates -or @($data.candidates).Count -lt 1) {
        throw "No usable WeChat db_storage found. Pass -DbDir manually."
    }
    $selected = @($data.candidates)[0]
    Write-Host "Selected: $($selected.path)"
    Write-Host "DB count: $($selected.db_count), score: $($selected.score)"
    return $selected.path
}

function Stop-WxDaemon {
    param([string]$WxCmd)
    try {
        & $WxCmd daemon stop | Out-Null
    } catch {
    }
}

function Infer-SelfWxid {
    param([string]$SelectedDbDir)
    if ($SelfWxid) {
        return $SelfWxid
    }
    $accountDir = Split-Path -Leaf (Split-Path -Parent $SelectedDbDir)
    if ($accountDir -match '^(wxid_.+)_([0-9a-zA-Z]+)$') {
        return $Matches[1]
    }
    return ""
}

if (-not (Test-Admin) -and -not $SkipKeyScan) {
    throw "Run PowerShell as Administrator. WeChat 4.x key scanning usually needs admin rights."
}

$weixin = Get-Process Weixin -ErrorAction SilentlyContinue
if (-not $weixin -and -not $SkipKeyScan) {
    throw "Weixin.exe was not found. Open and log in to WeChat first."
}

$python = Resolve-Python
Ensure-PythonDeps -Python $python
$wxCmd = Ensure-WxCli
$selectedDbDir = Find-DbDir -Python $python

$configPath = Join-Path $OutputRoot "config.json"
$keysPath = Join-Path $OutputRoot "all_keys.json"
$decryptedDir = Join-Path $OutputRoot "decrypted_wx_cli_all"
$exportDir = Join-Path $OutputRoot "exports_txt"

$config = [ordered]@{
    db_dir = $selectedDbDir
    keys_file = "all_keys.json"
    decrypted_dir = "decrypted_wx_cli_all"
    wechat_process = "Weixin.exe"
}
$config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8

if (-not $SkipKeyScan) {
    Write-Step "Scan running WeChat process and extract DB keys"
    Push-Location $OutputRoot
    try {
        & $wxCmd init --force | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "wx-cli init failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath $keysPath)) {
    throw "all_keys.json was not found. Cannot decrypt databases."
}

Write-Step "Decrypt matched databases"
$decryptOut = & $python (Join-Path $ToolRoot "decrypt_wx_cli_raw.py") `
    --config $configPath `
    --keys $keysPath `
    --out-dir $decryptedDir
if ($LASTEXITCODE -ne 0) {
    throw "Database decrypt failed with exit code $LASTEXITCODE"
}
$decryptOut | Out-Host

Write-Step "Export text chats"
$resolvedSelfWxid = Infer-SelfWxid -SelectedDbDir $selectedDbDir
if (-not $resolvedSelfWxid) {
    throw "Cannot infer self wxid from db_storage path. Pass -SelfWxid manually."
}
$exportArgs = @(
    (Join-Path $ToolRoot "export_wechat_text.py"),
    "--db-root", $decryptedDir,
    "--out-root", $exportDir,
    "--self-wxid", $resolvedSelfWxid
)
if ($TargetChat) {
    $exportArgs += @("--target-chat", $TargetChat)
}
$exportOut = & $python @exportArgs
if ($LASTEXITCODE -ne 0) {
    throw "Text export failed with exit code $LASTEXITCODE"
}
$exportOut | Out-Host
$exportJson = ($exportOut | Out-String | ConvertFrom-Json)

Stop-WxDaemon -WxCmd $wxCmd

$summaryPath = Join-Path $OutputRoot "run_summary.json"
$runSummary = [ordered]@{
    db_dir = $selectedDbDir
    output_root = $OutputRoot
    chats = $exportJson.chats
    messages = $exportJson.messages
    self_wxid = $exportJson.self_wxid
    all_chats = (Join-Path $exportDir "all_chats.txt")
    by_chat_dir = (Join-Path $exportDir "by_chat")
    summary_json = (Join-Path $exportDir "summary.json")
    single_chat = $exportJson.single_chat
    sensitive = [ordered]@{
        keys_file = $keysPath
        decrypted_dir = $decryptedDir
        cleaned = (-not $KeepSensitive) -or $CleanSensitive
    }
}
$runSummary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ((-not $KeepSensitive) -or $CleanSensitive) {
    Write-Step "Clean sensitive intermediate files"
    Remove-Item -LiteralPath $keysPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $decryptedDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Step "Done"
Write-Host "Output root: $OutputRoot"
Write-Host "All chats: $(Join-Path $exportDir 'all_chats.txt')"
Write-Host "By-chat dir: $(Join-Path $exportDir 'by_chat')"
if ($exportJson.single_chat -and $exportJson.single_chat.matched) {
    Write-Host "Single chat: $($exportJson.single_chat.file)"
}
Write-Host "Run summary: $summaryPath"
