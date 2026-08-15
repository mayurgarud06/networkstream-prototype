param(
    [string]$Api = "http://localhost:8080",
    [string]$GatewayId = "WIN-$env:COMPUTERNAME",
    [int]$Interval = 30,
    [switch]$DataPlane
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "networkstream-windows-agent.py"
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "Python was not found. Install Python 3 and make python.exe or py.exe available on PATH." }

$taskName = "NetworkStream-Windows-Gateway"
$arguments = "`"$scriptPath`" --api `"$Api`" --gateway-id `"$GatewayId`" --interval $Interval"
if ($DataPlane) { $arguments += " --data-plane" }
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "NetworkStream Windows gateway agent" -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "NetworkStream Windows gateway installed and started."
Write-Host "Task: $taskName"
Write-Host "Gateway: $GatewayId"
Write-Host "API: $Api"
Write-Host "Scan interval: $Interval seconds"
Write-Host "Data plane: $($DataPlane.IsPresent)"
