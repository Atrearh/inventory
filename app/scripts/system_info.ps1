# scripts/system_info.ps1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
function Clean-String($s) {
    if (!$s) { return "" }
    $s = ($s -replace '[\x00-\x1F\x7F]', '').Trim()
    return $s
}
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $bios = Get-CimInstance Win32_BIOS
    $baseboard = Get-CimInstance Win32_BaseBoard  # Добавляем получение информации о материнской плате
    $disks = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 -and $_.Size -gt 0 }
    $nics = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled }
    
    $isServerOS = $os.Caption -match 'Server'
    $roles = @()
    if ($isServerOS -and (Get-Command -Name Get-WindowsFeature -ErrorAction SilentlyContinue)) {
        try {
            $roles = Get-WindowsFeature | Where-Object { $_.Installed } | Select-Object -ExpandProperty Name | ForEach-Object { Clean-String $_ }
        } catch {
            Write-Warning "Не удалось получить роли сервера: $($_.Exception.Message)"
        }
    }
    
    $diskInfo = @($disks | ForEach-Object {
        @{
            DeviceID    = Clean-String $_.DeviceID
            total_space = [int64]$_.Size
            free_space  = [int64]$_.FreeSpace
        }
    })
    
    @{
        hostname      = Clean-String $env:COMPUTERNAME
        os_name       = Clean-String $os.Caption
        os_version    = Clean-String $os.Version
        cpu           = Clean-String (Get-CimInstance Win32_Processor).Name
        ram           = [math]::Round($cs.TotalPhysicalMemory / 1MB)
        mac_address   = ($nics | Select-Object -ExpandProperty MACAddress | Select-Object -First 1)
        motherboard   = Clean-String "$($baseboard.Manufacturer) $($baseboard.Product)"  # Используем Manufacturer и Product
        last_boot     = $os.LastBootUpTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
        is_virtual    = $cs.Model -match 'Virtual|VMware|Hyper-V'
        status        = "online"
        check_status  = "success"
        ip_address    = ($nics | Select-Object -ExpandProperty IPAddress | Where-Object {$_ -match '^\d+\.\d+\.\d+\.\d+$'} | Select-Object -First 1)
        disks         = $diskInfo
        roles         = $roles
    } | ConvertTo-Json -Depth 4 -Compress
} catch {
    @{
        hostname      = Clean-String $env:COMPUTERNAME
        status        = "online"
        check_status  = "failed"
        error         = Clean-String $_.Exception.Message
    } | ConvertTo-Json -Compress
}