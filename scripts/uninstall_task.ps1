param(
    [string]$TaskName = "Antigravity_Auto_Convo_Rename"
)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'." -ForegroundColor Green
} else {
    Write-Host "Scheduled task '$TaskName' is not registered." -ForegroundColor Yellow
}
