$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
function Clean-String($s) {if (-not $s) { return "" } ($s -replace '[\x00-\x1F\x7F]', '').Trim()}
try {
    $os = Get-CimInstance Win32_OperatingSystem -Property Caption, Version, LastBootUpTime
    $cs = Get-CimInstance Win32_ComputerSystem -Property TotalPhysicalMemory, Model
    $bios = Get-CimInstance Win32_BIOS
    $baseboard = Get-CimInstance Win32_BaseBoard -Property Manufacturer, Product
    $nics = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled }
    $processors = Get-CimInstance Win32_Processor -Property Name, NumberOfCores, NumberOfLogicalProcessors
    $video = Get-CimInstance Win32_VideoController -Property Name, DriverVersion
    $cpuInfo = @($processors | ForEach-Object {
        @{
            name = Clean-String $_.Name
            number_of_cores = [int]$_.NumberOfCores
            number_of_logical_processors = [int]$_.NumberOfLogicalProcessors
        }
    })
    $macAddresses = @($nics | Select-Object -ExpandProperty MACAddress | Where-Object { $_ } | ForEach-Object { Clean-String $_ })
    $ipAddresses = @($nics | Select-Object -ExpandProperty IPAddress | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } | ForEach-Object { Clean-String $_ })
    $videoInfo = @($video | ForEach-Object {
        @{
            name = Clean-String $_.Name
            driver_version = Clean-String $_.DriverVersion
        }
    })
    $result = @{
        hostname      = Clean-String $env:COMPUTERNAME
        os_name       = Clean-String $os.Caption
        os_version    = Clean-String $os.Version
        processors    = $cpuInfo
        ram           = [int64]([math]::Round($cs.TotalPhysicalMemory / 1MB))
        mac_addresses = $macAddresses
        ip_addresses  = $ipAddresses
        motherboard   = Clean-String "$($baseboard.Manufacturer) $($baseboard.Product)"
        last_boot     = $os.LastBootUpTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
        is_virtual    = [bool]($cs.Model -match 'Virtual|VMware|Hyper-V')
        video_cards   = $videoInfo
    }

    ConvertTo-Json -InputObject $result -Depth 10 -Compress
} catch {
    $errorResult = @{
        hostname = Clean-String $env:COMPUTERNAME
        error    = Clean-String $_.Exception.Message
    }
    Write-Error "Ошибка выполнения скрипта: $($_.Exception.Message)"
    ConvertTo-Json -InputObject $errorResult -Depth 2 -Compress
}