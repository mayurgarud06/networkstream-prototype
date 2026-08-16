param(
    [string]$Api = "http://localhost:8080",
    [string]$GatewayId = "WIN-$env:COMPUTERNAME",
    [int]$Interval = 15
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "networkstream-windows-agent.py"
$requirements = Join-Path $PSScriptRoot "requirements.txt"
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "Python was not found. Install Python 3 and make python.exe or py.exe available on PATH." }

& $python -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) { throw "Failed to install packet dataplane dependencies." }

$taskName = "NetworkStream-Windows-Gateway"
$arguments = "`"$scriptPath`" --api `"$Api`" --gateway-id `"$GatewayId`" --interval $Interval --data-plane"
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "NetworkStream packet dataplane gateway agent" -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "NetworkStream packet dataplane installed and started."
Write-Host "Task: $taskName"
Write-Host "Gateway: $GatewayId"
Write-Host "API: $Api"
Write-Host "Interval: $Interval seconds"
