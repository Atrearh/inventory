$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = $OutputEncoding = [Text.Encoding]::UTF8
function Clean-String($s) {
    if (!$s) { "" }
    else { ($s -replace '[\x00-\x1F\x7F]', '').Trim() -replace '\s+False$', '' }
}
try {
    $result = @{}
    $os = Get-CimInstance Win32_OperatingSystem
    $result.os_name = Clean-String $os.Caption
    $result.os_version = $os.Version
    $result.last_boot = if ($os.LastBootUpTime) { $os.LastBootUpTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
    $cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
    $result.cpu = Clean-String $cp
    $result.ram = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 0)
    $result.disks = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 } | ForEach-Object {
        @{
            DeviceID = $_.DeviceID
            TotalSpace = $_.Size
            FreeSpace = $_.FreeSpace
        }
    }
    $mb = (Get-CimInstance Win32_BaseBoard).Product
    $result.motherboard = Clean-String $mb
    $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled -eq $true } | Select-Object -First 1
    $result.ip_address = if ($adapter.IPAddress) { $adapter.IPAddress[0] } else { $null }
    $result.mac_address = if ($adapter.MACAddress) { $adapter.MACAddress } else { $null }
    $result.is_virtual = (Get-CimInstance Win32_ComputerSystem).Model -match "Virtual|VMware|Hyper-V"
    $result.roles = @()
    $result.status = "online"
    $result.check_status = "success"
    $result.hostname = $env:COMPUTERNAME
    $result | ConvertTo-Json -Depth 4 -Compress
} catch {
    Write-Error "system_info.ps1: $($_.Exception.Message)"
    @{
        hostname = $env:COMPUTERNAME
        check_status = "failed"
        error = $_.Exception.Message
    } | ConvertTo-Json -Compress
}