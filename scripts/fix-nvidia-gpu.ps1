# EagleSignal — recover a phantom / stuck NVIDIA dGPU (CM_PROB_PHANTOM / code 43).
# Run elevated (the .bat launcher self-elevates). Safe: it only restarts NVIDIA
# services and re-enumerates the dGPU; it never touches the Intel display.

$ErrorActionPreference = 'Continue'
Write-Host "=== EagleSignal NVIDIA dGPU recovery ===" -ForegroundColor Cyan

# Admin check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
          ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "NOT running as administrator — re-run via fix-nvidia-gpu.bat (it elevates)." -ForegroundColor Red
    exit 1
}

# Power-state warning
$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
if ($bat -and [int]$bat.BatteryStatus -eq 1) {
    Write-Host "WARNING: you are on BATTERY. The dGPU power-gates on battery — plug in AC for reliable GPU." -ForegroundColor Yellow
}

# 1) Restart NVIDIA container services
foreach ($svc in 'NvContainerLocalSystem','NVDisplay.ContainerLocalSystem') {
    try { Restart-Service -Name $svc -Force -ErrorAction Stop; Write-Host "restarted service: $svc" -ForegroundColor Green }
    catch { Write-Host "service $svc: $($_.Exception.Message)" }
}

# 2) Re-enumerate PCIe devices (brings back a phantom dGPU)
Write-Host "scanning for hardware changes..."
pnputil /scan-devices | Out-Host

# 3) Disable+enable the NVIDIA display node (clears a stuck/code-43 node)
$dev = Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -like '*NVIDIA*' }
if ($dev) {
    foreach ($d in $dev) {
        Write-Host "cycling device: $($d.FriendlyName)  [status=$($d.Status) problem=$($d.Problem)]"
        try { Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction Stop; Start-Sleep 2 }
        catch { Write-Host "  disable skipped: $($_.Exception.Message)" }
        try { Enable-PnpDevice  -InstanceId $d.InstanceId -Confirm:$false -ErrorAction Stop; Start-Sleep 3 }
        catch { Write-Host "  enable skipped: $($_.Exception.Message)" }
    }
} else {
    Write-Host "No NVIDIA display node present yet (still phantom)." -ForegroundColor Yellow
}

# 4) Verify
Write-Host "`n=== nvidia-smi ===" -ForegroundColor Cyan
$smi = "$env:SystemRoot\System32\nvidia-smi.exe"
if (Test-Path $smi) { & $smi } else { nvidia-smi }

Write-Host "`nIf it STILL fails:" -ForegroundColor Yellow
Write-Host "  1) Plug in the AC charger." -ForegroundColor Yellow
Write-Host "  2) Reboot (clears a phantom PCIe device almost every time)." -ForegroundColor Yellow
Write-Host "  3) For heavy/sustained GPU work, run on AC + Power mode 'Best performance'." -ForegroundColor Yellow
