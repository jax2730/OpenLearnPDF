[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,
    [int[]]$Pages = @(109, 111, 113),
    [double]$MinimumFreeSpaceGB = 1,
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$RunLabel = 'rtr4-5-2-2',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Requirement = 'pdf-inspector==1.14.1'

function Resolve-AbsolutePath([string]$PathValue) {
    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd('\', '/')
}

function Get-FreeSpaceGB([string]$PathValue) {
    $root = [System.IO.Path]::GetPathRoot((Resolve-AbsolutePath $PathValue))
    $drive = New-Object System.IO.DriveInfo($root)
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

function ConvertTo-WindowsProcessArgument([string]$Argument) {
    if ($Argument.Contains('"')) { throw 'Process argument contains an unsupported quote character.' }
    if ($Argument -match '\s') { return '"' + $Argument + '"' }
    return $Argument
}

function Write-Utf8Json([string]$PathValue, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText(
        $PathValue,
        $json + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$workspace = Resolve-AbsolutePath $WorkspaceRoot
$workspaceDrive = [System.IO.Path]::GetPathRoot($workspace)
if ($workspaceDrive -ieq 'C:\') {
    throw 'WorkspaceRoot must not be on the C drive.'
}
if (-not $Pages -or $Pages.Count -gt 20) {
    throw 'Pages must contain between 1 and 20 entries.'
}
if ($Pages | Where-Object { $_ -le 0 }) {
    throw 'Pages must contain positive one-based page numbers.'
}
$canonicalPages = @($Pages | Sort-Object -Unique)
$venvPath = Join-Path $workspace '.venv-pdf-inspector'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$cacheRoot = Join-Path $workspace '.cache\pdf-inspector'
$cacheEnvironment = [ordered]@{
    PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
    TEMP = Join-Path $cacheRoot 'tmp'
    TMP = Join-Path $cacheRoot 'tmp'
}
$outputParent = Join-Path $workspace 'data\probes\pdf-inspector'
$plannedOutput = Join-Path $outputParent ($RunLabel + '-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
$pdfPath = Join-Path $workspace 'RTR4-CN-v1.1.pdf'
$runnerPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\run-pdf-inspector-probe.py'
$plan = [ordered]@{
    dry_run = [bool]$DryRun
    requirement = $Requirement
    venv_path = $venvPath
    pdf_path = $pdfPath
    pages = $canonicalPages
    output_parent = $outputParent
    planned_output = $plannedOutput
    cache_environment = $cacheEnvironment
}
if ($DryRun) {
    $plan | ConvertTo-Json -Depth 5 -Compress
    exit 0
}

if (-not (Test-Path -LiteralPath $workspace -PathType Container)) {
    throw "WorkspaceRoot does not exist: $workspace"
}
$freeSpaceGB = Get-FreeSpaceGB $workspace
if ($freeSpaceGB -lt $MinimumFreeSpaceGB) {
    throw "Insufficient free disk space: ${freeSpaceGB}GB available; ${MinimumFreeSpaceGB}GB required."
}
if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf)) {
    throw "PDF not found: $pdfPath"
}
if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
    throw "Probe runner not found: $runnerPath"
}

foreach ($entry in $cacheEnvironment.GetEnumerator()) {
    [System.IO.Directory]::CreateDirectory($entry.Value) | Out-Null
    Set-Item -LiteralPath "Env:$($entry.Key)" -Value $entry.Value
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3.12 -m venv $venvPath
    } else {
        $python = Get-Command python -ErrorAction Stop
        & $python.Source -m venv $venvPath
    }
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create pdf-inspector virtual environment.' }
}

$installedVersion = & $venvPython -c "import importlib.metadata; print(importlib.metadata.version('pdf-inspector'))" 2>$null
if ($LASTEXITCODE -ne 0 -or $installedVersion.Trim() -ne '1.14.1') {
    & $venvPython -m pip install --disable-pip-version-check $Requirement
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install pinned pdf-inspector package.' }
}

[System.IO.Directory]::CreateDirectory($outputParent) | Out-Null
$outputDir = $plannedOutput
$suffix = 1
while (Test-Path -LiteralPath $outputDir) {
    $outputDir = "$plannedOutput-$suffix"
    $suffix += 1
}

$stdoutPath = Join-Path $cacheEnvironment.TEMP ('probe-' + [guid]::NewGuid().ToString('N') + '.stdout.log')
$stderrPath = Join-Path $cacheEnvironment.TEMP ('probe-' + [guid]::NewGuid().ToString('N') + '.stderr.log')
$arguments = @($runnerPath, '--pdf', $pdfPath, '--output', $outputDir, '--pages') + @($canonicalPages | ForEach-Object { "$_" })
$processArguments = @($arguments | ForEach-Object { ConvertTo-WindowsProcessArgument $_ })
$process = Start-Process -FilePath $venvPython -ArgumentList $processArguments -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -WindowStyle Hidden -PassThru
$null = $process.Handle
$tracked = New-Object 'System.Collections.Generic.HashSet[int]'
$null = $tracked.Add([int]$process.Id)
$peakWorkingSetBytes = [long]0
while (-not $process.HasExited) {
    $processes = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, WorkingSetSize -ErrorAction SilentlyContinue)
    do {
        $added = $false
        foreach ($candidate in $processes) {
            if ($tracked.Contains([int]$candidate.ParentProcessId) -and $tracked.Add([int]$candidate.ProcessId)) {
                $added = $true
            }
        }
    } while ($added)
    $workingSetBytes = [long]0
    foreach ($candidate in $processes) {
        if ($tracked.Contains([int]$candidate.ProcessId)) {
            $workingSetBytes += [long]$candidate.WorkingSetSize
        }
    }
    if ($workingSetBytes -gt $peakWorkingSetBytes) {
        $peakWorkingSetBytes = $workingSetBytes
    }
    Start-Sleep -Milliseconds 200
    $process.Refresh()
}
$process.WaitForExit()
if ($process.ExitCode -ne 0) {
    $errorText = Get-Content -Raw -LiteralPath $stderrPath -ErrorAction SilentlyContinue
    throw "pdf-inspector probe failed with exit code $($process.ExitCode): $errorText"
}
if (-not (Test-Path -LiteralPath $outputDir -PathType Container)) {
    throw "Probe completed without output: $outputDir"
}

$reportPath = Join-Path $outputDir 'report.json'
$report = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath | ConvertFrom-Json
$report | Add-Member -NotePropertyName peak_working_set_mb -NotePropertyValue ([math]::Round($peakWorkingSetBytes / 1MB, 1)) -Force
Write-Utf8Json $reportPath $report
Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

[ordered]@{
    output_dir = $outputDir
    pages = $canonicalPages
    peak_working_set_mb = $report.peak_working_set_mb
    recommendation = $report.recommendation
} | ConvertTo-Json -Compress
