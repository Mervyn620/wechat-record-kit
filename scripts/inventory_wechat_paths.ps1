[CmdletBinding()]
param(
    [string[]]$Roots,
    [string]$Out,
    [int]$MaxDepth = 8,
    [switch]$IncludeWeCom,
    [string[]]$ExcludeDirectoryNames = @(".git", ".venv", "node_modules", "__pycache__", "runs", "work", "exports", "secrets")
)

$ErrorActionPreference = "Stop"

function Add-ExistingPath {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Path
    )
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    try {
        $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
        if (-not $List.Contains($resolved)) {
            [void]$List.Add($resolved)
        }
    } catch {
        return
    }
}

function Read-WeChatConfiguredRoot {
    param([System.Collections.Generic.List[string]]$List)

    $appData = [Environment]::GetFolderPath("ApplicationData")
    $configPath = Join-Path $appData "Tencent\WeChat\All Users\config\3ebffe94.ini"
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return $null
    }

    $rawItem = Get-Content -LiteralPath $configPath -ErrorAction SilentlyContinue | Select-Object -First 1
    $raw = if ($null -ne $rawItem) { [string]$rawItem } else { $null }
    if (-not [string]::IsNullOrWhiteSpace($raw)) {
        Add-ExistingPath -List $List -Path $raw.Trim()
    }

    return [PSCustomObject]@{
        path = $configPath
        exists = $true
        first_line = $raw
    }
}

function Add-InstallCandidate {
    param(
        [System.Collections.Generic.List[object]]$List,
        [string]$Path,
        [string]$Source
    )
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    $candidate = $Path.Trim('"')
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $candidate = Split-Path -Parent $candidate
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        return
    }

    try {
        $resolved = (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
    } catch {
        return
    }

    foreach ($item in $List) {
        if ($item.path -eq $resolved) {
            return
        }
    }

    $exeCandidates = @(
        (Join-Path $resolved "WXWork.exe"),
        (Join-Path $resolved "WeCom.exe"),
        (Join-Path $resolved "WXWorkLauncher.exe")
    )
    $exe = $exeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1

    [void]$List.Add([PSCustomObject]@{
        path = $resolved
        source = $Source
        exe = $exe
        last_write_time = (Get-Item -LiteralPath $resolved -Force).LastWriteTime.ToString("o")
    })
}

function Find-WeComInstallCandidates {
    $items = New-Object "System.Collections.Generic.List[object]"

    $knownPaths = New-Object "System.Collections.Generic.List[string]"
    $envPaths = @(
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)},
        $env:LocalAppData,
        $env:AppData
    )
    foreach ($base in $envPaths) {
        if (-not [string]::IsNullOrWhiteSpace($base)) {
            [void]$knownPaths.Add((Join-Path $base "WXWork"))
            [void]$knownPaths.Add((Join-Path $base "Tencent\WXWork"))
        }
    }

    try {
        foreach ($drive in Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) {
            [void]$knownPaths.Add((Join-Path $drive.Root "Software\WXWork"))
        }
    } catch {
    }

    foreach ($path in $knownPaths) {
        Add-InstallCandidate -List $items -Path $path -Source "known-path"
    }

    $registryRoots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($registryRoot in $registryRoots) {
        try {
            $apps = Get-ItemProperty -Path $registryRoot -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.DisplayName -match "企业微信|WXWork|WeCom|WeChat Work"
                }
            foreach ($app in $apps) {
                Add-InstallCandidate -List $items -Path $app.InstallLocation -Source "registry:InstallLocation"
                Add-InstallCandidate -List $items -Path $app.DisplayIcon -Source "registry:DisplayIcon"
                Add-InstallCandidate -List $items -Path $app.UninstallString -Source "registry:UninstallString"
            }
        } catch {
        }
    }

    return $items
}

function Get-LimitedFiles {
    param(
        [string]$Root,
        [int]$MaxDepth,
        [string[]]$ExcludeDirectoryNames
    )

    $queue = New-Object "System.Collections.Generic.Queue[object]"
    $queue.Enqueue([PSCustomObject]@{ Path = $Root; Depth = 0 })

    while ($queue.Count -gt 0) {
        $item = $queue.Dequeue()
        if ($item.Depth -gt $MaxDepth) {
            continue
        }

        try {
            Get-ChildItem -LiteralPath $item.Path -Force -File -ErrorAction SilentlyContinue
        } catch {
        }

        if ($item.Depth -eq $MaxDepth) {
            continue
        }

        try {
            $dirs = Get-ChildItem -LiteralPath $item.Path -Force -Directory -ErrorAction SilentlyContinue
            foreach ($dir in $dirs) {
                if ($ExcludeDirectoryNames -contains $dir.Name) {
                    continue
                }
                $queue.Enqueue([PSCustomObject]@{ Path = $dir.FullName; Depth = ($item.Depth + 1) })
            }
        } catch {
        }
    }
}

function Convert-FileInfo {
    param([System.IO.FileInfo]$File)
    [PSCustomObject]@{
        path = $File.FullName
        name = $File.Name
        directory = $File.DirectoryName
        size_bytes = $File.Length
        last_write_time = $File.LastWriteTime.ToString("o")
    }
}

$candidateRoots = New-Object "System.Collections.Generic.List[string]"

if ($Roots -and $Roots.Count -gt 0) {
    foreach ($root in $Roots) {
        Add-ExistingPath -List $candidateRoots -Path $root
    }
} else {
    $documents = [Environment]::GetFolderPath("MyDocuments")
    $userProfile = [Environment]::GetFolderPath("UserProfile")
    $appData = [Environment]::GetFolderPath("ApplicationData")
    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")

    Add-ExistingPath -List $candidateRoots -Path (Join-Path $documents "WeChat Files")
    Add-ExistingPath -List $candidateRoots -Path (Join-Path $userProfile "Documents\WeChat Files")
    Add-ExistingPath -List $candidateRoots -Path (Join-Path $appData "Tencent\WeChat")
    Add-ExistingPath -List $candidateRoots -Path (Join-Path $localAppData "Tencent\WeChat")

    if ($IncludeWeCom) {
        Add-ExistingPath -List $candidateRoots -Path (Join-Path $documents "WXWork")
        Add-ExistingPath -List $candidateRoots -Path (Join-Path $userProfile "Documents\WXWork")
        Add-ExistingPath -List $candidateRoots -Path (Join-Path $appData "Tencent\WXWork")
        Add-ExistingPath -List $candidateRoots -Path (Join-Path $localAppData "Tencent\WXWork")
    }
}

$configInfo = Read-WeChatConfiguredRoot -List $candidateRoots

$dbNamePattern = '^(MSG.*|MicroMsg|MediaMSG.*|PublicMsg|Favorite|OpenIM.*|message_.*|contact.*|session.*|biz.*|fts.*).*\.(db|sqlite|sqlite3)$'
$mediaDirPattern = '\\FileStorage\\(File|Image|Video|Voice|Temp)(\\|$)'
$dbCandidates = New-Object "System.Collections.Generic.List[object]"
$mediaCandidates = New-Object "System.Collections.Generic.List[object]"
$accountDirs = New-Object "System.Collections.Generic.List[object]"
$installCandidates = New-Object "System.Collections.Generic.List[object]"

if ($IncludeWeCom) {
    $foundInstalls = Find-WeComInstallCandidates
    foreach ($install in $foundInstalls) {
        [void]$installCandidates.Add($install)
    }
}

foreach ($root in $candidateRoots) {
    try {
        $topDirs = Get-ChildItem -LiteralPath $root -Force -Directory -ErrorAction SilentlyContinue
        foreach ($dir in $topDirs) {
            if ($dir.Name -like "wxid_*" -or $dir.Name -like "wxuser_*" -or $dir.Name -match "^[A-Za-z0-9_\-]{4,}$") {
                [void]$accountDirs.Add([PSCustomObject]@{
                    path = $dir.FullName
                    name = $dir.Name
                    last_write_time = $dir.LastWriteTime.ToString("o")
                })
            }
        }
    } catch {
    }

    $files = Get-LimitedFiles -Root $root -MaxDepth $MaxDepth -ExcludeDirectoryNames $ExcludeDirectoryNames
    foreach ($file in $files) {
        if ($file.Name -match $dbNamePattern) {
            [void]$dbCandidates.Add((Convert-FileInfo -File $file))
        } elseif ($file.FullName -match $mediaDirPattern) {
            [void]$mediaCandidates.Add((Convert-FileInfo -File $file))
        }
    }
}

$manifest = [PSCustomObject]@{
    generated_at = (Get-Date).ToString("o")
    machine = $env:COMPUTERNAME
    user = $env:USERNAME
    max_depth = $MaxDepth
    excluded_directory_names = $ExcludeDirectoryNames
    roots = $candidateRoots.ToArray()
    config = $configInfo
    account_dirs = $accountDirs.ToArray()
    install_candidates = $installCandidates.ToArray()
    db_candidates = $dbCandidates.ToArray()
    media_candidates = $mediaCandidates.ToArray()
    notes = @(
        "Read-only inventory. It does not read message content, decrypt databases, or extract keys.",
        "DB file names are heuristics. Confirm actual schema with inspect_decrypted_sqlite.py after authorized decryption."
    )
}

$json = $manifest | ConvertTo-Json -Depth 6

if (-not [string]::IsNullOrWhiteSpace($Out)) {
    $outDir = Split-Path -Parent $Out
    if (-not [string]::IsNullOrWhiteSpace($outDir) -and -not (Test-Path -LiteralPath $outDir)) {
        New-Item -ItemType Directory -Path $outDir | Out-Null
    }
    Set-Content -LiteralPath $Out -Value $json -Encoding UTF8
} else {
    $json
}
