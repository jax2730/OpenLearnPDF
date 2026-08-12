[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,
    [switch]$DryRun,
    [double]$MinimumFreeSpaceGB = 25
)

$ErrorActionPreference = "Stop"
$MinerURequirement = "mineru[pipeline]==3.4.4"
$TorchRequirement = "torch==2.13.0+cu130"
$TorchvisionRequirement = "torchvision==0.28.0+cu130"
$TorchIndexUrl = "https://download.pytorch.org/whl/cu130"
$CompatibilityRequirements = @('six==1.17.0')
$ModelId = 'OpenDataLab/PDF-Extract-Kit-1.0'
$ModelRevision = 'master'

function Resolve-AbsolutePath([string]$PathValue) {
    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd('\', '/')
}

function Test-ProtectedPath([string]$PathValue) {
    $normalized = (Resolve-AbsolutePath $PathValue).Replace('/', '\')
    return ($normalized -match '(?i)(^|\\)\.venv-pdf(\\|$)') -or
        ($normalized -match '(?i)(^|\\)backend\\\.venv(\\|$)')
}

function Get-FreeSpaceGB([string]$PathValue) {
    $root = [System.IO.Path]::GetPathRoot((Resolve-AbsolutePath $PathValue))
    $drive = New-Object System.IO.DriveInfo($root)
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

function Find-PythonLauncher {
    foreach ($version in @('3.10', '3.11', '3.12')) {
        & py "-$version" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == tuple(map(int, '$version'.split('.'))) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Version = $version; Command = 'py'; Prefix = @("-$version") }
        }
    }
    throw "No supported Python found. Required: Python 3.10-3.12."
}

function Write-Utf8Json([string]$PathValue, [object]$Value) {
    $parent = Split-Path -Parent $PathValue
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    $json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($PathValue, $json + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-CacheEnvironment([string]$WorkspacePath) {
    $cacheRoot = Join-Path $WorkspacePath '.cache'
    $huggingFaceRoot = Join-Path $cacheRoot 'huggingface'
    $tempRoot = Join-Path $cacheRoot 'tmp'
    return [ordered]@{
        UV_CACHE_DIR = Join-Path $cacheRoot 'uv'
        PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
        MODELSCOPE_CACHE = Join-Path $cacheRoot 'modelscope'
        HF_HOME = $huggingFaceRoot
        HUGGINGFACE_HUB_CACHE = Join-Path $huggingFaceRoot 'hub'
        MINERU_TOOLS_CONFIG_JSON = Join-Path (Join-Path $cacheRoot 'mineru') 'mineru.json'
        TEMP = $tempRoot
        TMP = $tempRoot
    }
}

function Get-ModelFingerprint(
    [string]$ModelRoot,
    [string]$ModelId,
    [string]$RequestedRevision
) {
    $result = [ordered]@{
        model_id = $ModelId
        requested_revision = $RequestedRevision
        snapshot_path = $ModelRoot
        present = Test-Path -LiteralPath $ModelRoot -PathType Container
        file_count = 0
        total_bytes = 0
        manifest_sha256 = $null
    }
    if (-not $result.present) { return $result }

    $manifestRows = New-Object System.Collections.Generic.List[string]
    $files = @(Get-ChildItem -LiteralPath $ModelRoot -Recurse -File | Sort-Object FullName)
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($ModelRoot.Length + 1).Replace('\', '/')
        $fileHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $manifestRows.Add("$relativePath`t$($file.Length)`t$fileHash")
        $result.total_bytes += $file.Length
    }
    $result.file_count = $files.Count
    $manifest = [string]::Join("`n", $manifestRows)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $result.manifest_sha256 = ([System.BitConverter]::ToString(
        $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($manifest))
    )).Replace('-', '').ToLowerInvariant()
    return $result
}

$workspace = Resolve-AbsolutePath $WorkspaceRoot
$venvPath = Join-Path $workspace '.venv-mineru'
if ((Test-ProtectedPath $workspace) -or (Test-ProtectedPath $venvPath)) {
    throw "Refusing protected environment path: $venvPath"
}

$python = Find-PythonLauncher
$uv = Get-Command uv -ErrorAction SilentlyContinue
$installer = if ($null -ne $uv) { 'uv' } else { 'venv-pip' }
$freeSpaceGB = Get-FreeSpaceGB $workspace
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$cacheEnvironment = Get-CacheEnvironment $workspace
$plan = [ordered]@{
    dry_run = [bool]$DryRun
    workspace_root = $workspace
    venv_path = $venvPath
    python_version = $python.Version
    installer = $installer
    mineru_requirement = $MinerURequirement
    torch_requirement = $TorchRequirement
    torchvision_requirement = $TorchvisionRequirement
    torch_index_url = $TorchIndexUrl
    compatibility_requirements = $CompatibilityRequirements
    model_id = $ModelId
    model_revision = $ModelRevision
    minimum_free_space_gb = $MinimumFreeSpaceGB
    free_space_gb = $freeSpaceGB
    cache_environment = $cacheEnvironment
}

if ($DryRun) {
    $plan | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
if ($freeSpaceGB -lt $MinimumFreeSpaceGB) {
    throw "Insufficient free disk space: ${freeSpaceGB}GB available; ${MinimumFreeSpaceGB}GB required."
}

foreach ($entry in $cacheEnvironment.GetEnumerator()) {
    $directory = if ($entry.Key -eq 'MINERU_TOOLS_CONFIG_JSON') { Split-Path -Parent $entry.Value } else { $entry.Value }
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    Set-Item -LiteralPath "Env:$($entry.Key)" -Value $entry.Value
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    if ($installer -eq 'uv') {
        & $uv.Source venv --python $python.Version $venvPath
    } else {
        & $python.Command @($python.Prefix) -m venv $venvPath
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to create isolated MinerU environment." }
}

if ($installer -eq 'venv-pip') {
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip in isolated MinerU environment." }
}

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    if ($installer -eq 'uv') {
        & $uv.Source pip install --python $venvPython --index-url $TorchIndexUrl --upgrade $TorchRequirement $TorchvisionRequirement
    } else {
        & $venvPython -m pip install --index-url $TorchIndexUrl --upgrade $TorchRequirement $TorchvisionRequirement
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to install CUDA-enabled PyTorch from $TorchIndexUrl." }
}

if ($installer -eq 'uv') {
    & $uv.Source pip install --python $venvPython --upgrade $MinerURequirement @CompatibilityRequirements
} else {
    & $venvPython -m pip install --upgrade $MinerURequirement @CompatibilityRequirements
}
if ($LASTEXITCODE -ne 0) { throw "Failed to install $MinerURequirement." }

$packageJson = & $venvPython -c "import importlib.metadata,json; names=['mineru','torch','torchvision','onnxruntime','transformers','modelscope','huggingface-hub','six']; print(json.dumps({n: importlib.metadata.version(n) for n in names if n in {d.metadata['Name'].lower() for d in importlib.metadata.distributions()}}, sort_keys=True))"
$packages = $packageJson | ConvertFrom-Json
$pythonFullVersion = (& $venvPython -c "import platform; print(platform.python_version())").Trim()
$mineruExe = Join-Path $venvPath 'Scripts\mineru.exe'
$helpText = (& $mineruExe --help 2>&1 | Out-String)
$sha = [System.Security.Cryptography.SHA256]::Create()
$helpHash = ([System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($helpText)))).Replace('-', '').ToLowerInvariant()
$gpuInfo = $null
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $gpuInfo = (& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits 2>$null | Out-String).Trim()
}
$modelRoot = Join-Path $cacheEnvironment.MODELSCOPE_CACHE 'models\OpenDataLab--PDF-Extract-Kit-1.0\snapshots\master'
$modelFingerprint = Get-ModelFingerprint $modelRoot $ModelId $ModelRevision
$metadata = [ordered]@{
    schema_version = 1
    recorded_at = [DateTime]::UtcNow.ToString('o')
    environment_path = $venvPath
    installer = $installer
    python = $pythonFullVersion
    requirement = $MinerURequirement
    compatibility_requirements = $CompatibilityRequirements
    torch_index_url = $TorchIndexUrl
    packages = $packages
    cli = [ordered]@{ executable = $mineruExe; help_sha256 = $helpHash }
    models = [ordered]@{ source = 'modelscope'; pipeline = $modelFingerprint; cache_paths = @($cacheEnvironment.MODELSCOPE_CACHE) }
    cache_environment = $cacheEnvironment
    gpu = $gpuInfo
}
Write-Utf8Json (Join-Path $workspace 'data\toolchains\mineru.json') $metadata
$metadata | ConvertTo-Json -Depth 8
