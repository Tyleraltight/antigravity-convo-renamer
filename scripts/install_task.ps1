param(
    [string]$TaskName = "Antigravity_Auto_Convo_Rename",
    [int]$IntervalMinutes = 15
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VbsPath = Join-Path $PSScriptRoot "run_silent.vbs"
$RenamerPath = Join-Path $RepoRoot "renamer.py"

$VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PyExe = if (Test-Path $VenvPy) { $VenvPy } else { (Get-Command python -ErrorAction Stop).Source }

Write-Host "Running dry-run verification..." -ForegroundColor Cyan
& $PyExe $RenamerPath --dry-run | Out-Null

$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`""
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Scheduled task '$TaskName' registered (every $IntervalMinutes min)." -ForegroundColor Green
