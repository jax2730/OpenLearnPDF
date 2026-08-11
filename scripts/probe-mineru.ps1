[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,
    [switch]$DryRun,
    [double]$MinimumFreeSpaceGB = 25
)

$ErrorActionPreference = "Stop"
$ModelId = 'OpenDataLab/PDF-Extract-Kit-1.0'
$ModelRevision = 'master'

function Resolve-AbsolutePath([string]$PathValue) {
    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd('\', '/')
}

function Get-FreeSpaceGB([string]$PathValue) {
    $root = [System.IO.Path]::GetPathRoot((Resolve-AbsolutePath $PathValue))
    $drive = New-Object System.IO.DriveInfo($root)
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

function Write-Utf8Json([string]$PathValue, [object]$Value) {
    $parent = Split-Path -Parent $PathValue
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    $json = $Value | ConvertTo-Json -Depth 12
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

function ConvertTo-WindowsProcessArgument([string]$Argument) {
    if ($Argument.Contains('"')) { throw "Process argument contains an unsupported quote character." }
    if ($Argument -match '\s') { return '"' + $Argument + '"' }
    return $Argument
}

function Stop-ProcessTree([int]$ProcessId) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue)
    foreach ($child in $children) { Stop-ProcessTree -ProcessId $child.ProcessId }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
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
$pdfPath = Join-Path $workspace 'RTR4-CN-v1.1.pdf'
$venvPath = Join-Path $workspace '.venv-mineru'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$validatorPath = Join-Path $PSScriptRoot 'validate-mineru-output.py'
$mineruExe = Join-Path $venvPath 'Scripts\mineru.exe'
$modelDownloadExe = Join-Path $venvPath 'Scripts\mineru-models-download.exe'
$canonicalPages = @(104, 105, 106)
$startPage = 103
$endPage = 105
$outputParent = Join-Path $workspace 'data\books\rtr4-cn\parses'
$plannedOutput = Join-Path $outputParent ('mineru-probe-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
$commandArgs = @('-p', $pdfPath, '-o', $plannedOutput, '-b', 'pipeline', '-s', "$startPage", '-e', "$endPage")
$processArguments = @($commandArgs | ForEach-Object { ConvertTo-WindowsProcessArgument $_ })
$freeSpaceGB = Get-FreeSpaceGB $workspace
$cacheEnvironment = Get-CacheEnvironment $workspace
$plan = [ordered]@{
    dry_run = [bool]$DryRun
    backend = 'pipeline'
    canonical_pages = $canonicalPages
    mineru_start_page = $startPage
    mineru_end_page = $endPage
    free_space_gb = $freeSpaceGB
    minimum_free_space_gb = $MinimumFreeSpaceGB
    command = @($mineruExe) + $commandArgs
    process_arguments = $processArguments
    model_download_command = @($modelDownloadExe, '--source', 'modelscope', '--model_type', 'pipeline')
    cache_environment = $cacheEnvironment
}
if ($DryRun) {
    $plan | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
if ($freeSpaceGB -lt $MinimumFreeSpaceGB) {
    throw "Insufficient free disk space: ${freeSpaceGB}GB available; ${MinimumFreeSpaceGB}GB required."
}
if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf)) { throw "PDF not found: $pdfPath" }
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) { throw "MinerU Python not found: $venvPython" }
if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) { throw "MinerU output validator not found: $validatorPath" }
if (-not (Test-Path -LiteralPath $mineruExe -PathType Leaf)) { throw "MinerU executable not found: $mineruExe" }
if (-not (Test-Path -LiteralPath $modelDownloadExe -PathType Leaf)) { throw "MinerU model downloader not found: $modelDownloadExe" }

foreach ($entry in $cacheEnvironment.GetEnumerator()) {
    $directory = if ($entry.Key -eq 'MINERU_TOOLS_CONFIG_JSON') { Split-Path -Parent $entry.Value } else { $entry.Value }
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    Set-Item -LiteralPath "Env:$($entry.Key)" -Value $entry.Value
}

[System.IO.Directory]::CreateDirectory($outputParent) | Out-Null
$outputDir = $plannedOutput
$suffix = 1
while (Test-Path -LiteralPath $outputDir) {
    $outputDir = "$plannedOutput-$suffix"
    $suffix += 1
}
[System.IO.Directory]::CreateDirectory($outputDir) | Out-Null
$commandArgs[3] = $outputDir
$processArguments = @($commandArgs | ForEach-Object { ConvertTo-WindowsProcessArgument $_ })
$stdoutPath = Join-Path $outputDir 'stdout.log'
$stderrPath = Join-Path $outputDir 'stderr.log'
$modelStdoutPath = Join-Path $outputDir 'model-download.stdout.log'
$modelStderrPath = Join-Path $outputDir 'model-download.stderr.log'
$validationStdoutPath = Join-Path $outputDir 'validation.stdout.log'
$validationStderrPath = Join-Path $outputDir 'validation.stderr.log'
$stopMarker = Join-Path $outputDir '.gpu-monitor-stop'
$toolchainPath = Join-Path $workspace 'data\toolchains\mineru.json'
$modelRoot = Join-Path $cacheEnvironment.MODELSCOPE_CACHE 'models\OpenDataLab--PDF-Extract-Kit-1.0\snapshots\master'

$env:MINERU_MODEL_SOURCE = 'modelscope'
$startedAt = [DateTime]::UtcNow
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$phase = 'model-download'
$failureMessage = $null
$exitCode = -1
$modelDownloadExitCode = -1
$process = $null
$processId = $null
$modelProcessId = $null
$gpuJob = $null
$gpuBaselineMB = $null
$gpuPeakTotalMB = $null
$validation = $null

try {
    $modelArguments = @('--source', 'modelscope', '--model_type', 'pipeline')
    $modelProcess = Start-Process -FilePath $modelDownloadExe -ArgumentList $modelArguments -RedirectStandardOutput $modelStdoutPath -RedirectStandardError $modelStderrPath -NoNewWindow -PassThru
    $modelProcessId = $modelProcess.Id
    $null = $modelProcess.Handle
    $modelProcess.WaitForExit()
    $modelDownloadExitCode = $modelProcess.ExitCode
    if ($modelDownloadExitCode -ne 0) { throw "Pipeline model download failed with exit code $modelDownloadExitCode." }

    $modelFingerprint = Get-ModelFingerprint $modelRoot $ModelId $ModelRevision
    if (-not $modelFingerprint.present) { throw "Pipeline model snapshot not found after download: $modelRoot" }
    if (Test-Path -LiteralPath $toolchainPath -PathType Leaf) {
        $toolchainForUpdate = Get-Content -Raw -Encoding UTF8 -LiteralPath $toolchainPath | ConvertFrom-Json
        $toolchainForUpdate.models | Add-Member -NotePropertyName pipeline -NotePropertyValue $modelFingerprint -Force
        Write-Utf8Json $toolchainPath $toolchainForUpdate
    }

    $phase = 'parse'
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $baselineSamples = @(& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null)
        if ($baselineSamples.Count -gt 0) { $gpuBaselineMB = [int]$baselineSamples[0].Trim() }
        $gpuJob = Start-Job -ArgumentList $stopMarker -ScriptBlock {
            param($Marker)
            $peak = 0
            while (-not (Test-Path -LiteralPath $Marker)) {
                $samples = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null
                foreach ($sample in $samples) {
                    $value = 0
                    if ([int]::TryParse($sample.Trim(), [ref]$value) -and $value -gt $peak) { $peak = $value }
                }
                Start-Sleep -Milliseconds 750
            }
            return $peak
        }
    }

    $process = Start-Process -FilePath $mineruExe -ArgumentList $processArguments -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -NoNewWindow -PassThru
    $processId = $process.Id
    $null = $process.Handle
    $process.WaitForExit()
    $exitCode = $process.ExitCode
    if ($exitCode -ne 0) { throw "MinerU exited with code $exitCode." }

    $phase = 'validate-output'
    $validationJson = & $venvPython $validatorPath $outputDir 2> $validationStderrPath
    $validationExitCode = $LASTEXITCODE
    [System.IO.File]::WriteAllText($validationStdoutPath, (($validationJson | Out-String).Trim() + [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))
    if ($validationExitCode -ne 0) { throw "Native output validation command failed." }
    $validation = $validationJson | ConvertFrom-Json
    if ($validation.content_v2_count -ne 1) { throw "Expected exactly one content_list_v2 JSON, found $($validation.content_v2_count)." }
    if ($validation.page_count -ne $canonicalPages.Count) { throw "Expected $($canonicalPages.Count) parsed pages, found $($validation.page_count)." }
    if ($validation.markdown_count -lt 1) { throw "MinerU produced no Markdown output." }
    if ($validation.json_count -lt 1) { throw "MinerU produced no JSON output." }
    if ($validation.asset_count -lt 1) { throw "MinerU produced no image/formula assets." }
    if ($validation.nonempty_page_count -ne $canonicalPages.Count) { throw "One or more parsed pages contain no blocks." }
    if ($validation.markdown_nonempty_count -lt 1) { throw "MinerU Markdown output is empty." }
    if ($validation.asset_nonempty_count -lt 1) { throw "MinerU image/formula assets are empty." }
    if ($validation.equation_block_count -lt 1) { throw "MinerU produced no display-equation block." }
    if ($validation.image_block_count -lt 1) { throw "MinerU produced no image block." }
    if ($validation.referenced_asset_count -lt 1) { throw "MinerU JSON references no assets." }
    if ($validation.missing_referenced_asset_count -ne 0) { throw "MinerU JSON references missing or empty assets." }
} catch {
    $failureMessage = "$phase`: $($_.Exception.Message)"
} finally {
    $stopwatch.Stop()
    if ($null -ne $gpuJob) {
        [System.IO.File]::WriteAllText($stopMarker, 'stop')
        Wait-Job $gpuJob | Out-Null
        try {
            $gpuResult = Receive-Job $gpuJob
            $gpuPeakTotalMB = [int]$gpuResult
        } finally {
            Remove-Job $gpuJob -Force
        }
    }
    if (Test-Path -LiteralPath $stopMarker) { Remove-Item -LiteralPath $stopMarker -Force }
    if ($null -ne $failureMessage) {
        if ($null -ne $processId) { Stop-ProcessTree -ProcessId $processId }
        if ($null -ne $modelProcessId) { Stop-ProcessTree -ProcessId $modelProcessId }
    }
}

$artifacts = @(Get-ChildItem -LiteralPath $outputDir -Recurse -File | ForEach-Object {
    [ordered]@{ path = $_.FullName.Substring($outputDir.Length + 1); bytes = $_.Length }
})
$toolchain = if (Test-Path -LiteralPath $toolchainPath) { Get-Content -Raw -Encoding UTF8 -LiteralPath $toolchainPath | ConvertFrom-Json } else { $null }
$gpuDeltaMB = if ($null -ne $gpuPeakTotalMB -and $null -ne $gpuBaselineMB) { [math]::Max(0, $gpuPeakTotalMB - $gpuBaselineMB) } else { $null }
$probe = [ordered]@{
    schema_version = 1
    started_at = $startedAt.ToString('o')
    elapsed_seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
    exit_code = $exitCode
    model_download_exit_code = $modelDownloadExitCode
    status = if ($null -eq $failureMessage -and $exitCode -eq 0) { 'succeeded' } else { 'failed' }
    error = $failureMessage
    source_pdf = $pdfPath
    canonical_pages = $canonicalPages
    mineru_page_range = @($startPage, $endPage)
    backend = 'pipeline'
    cache_environment = $cacheEnvironment
    command = @($mineruExe) + $commandArgs
    gpu_memory_metric = 'device_global_memory_used_mb'
    gpu_baseline_total_memory_used_mb = $gpuBaselineMB
    gpu_peak_total_memory_used_mb = $gpuPeakTotalMB
    gpu_peak_delta_from_baseline_mb = $gpuDeltaMB
    output_validation = $validation
    output_dir = $outputDir
    artifacts = $artifacts
    toolchain = $toolchain
}
Write-Utf8Json (Join-Path $outputDir 'probe.json') $probe
$probe | ConvertTo-Json -Depth 12
if ($probe.status -ne 'succeeded') { throw "MinerU probe failed. Logs preserved in $outputDir. $failureMessage" }
