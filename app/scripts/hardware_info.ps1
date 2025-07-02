$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
function Clean-String($s) {if (-not $s) { return "" }($s -replace '[\x00-\x1F\x7F]', '').Trim()}
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $bios = Get-CimInstance Win32_BIOS
    $baseboard = Get-CimInstance Win32_BaseBoard
    $nics = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled }
    $processors = Get-CimInstance Win32_Processor
    $roles = @()
    if (Get-Command -Name Get-WindowsFeature -ErrorAction SilentlyContinue){try {$roles = Get-WindowsFeature | Where-Object { $_.Installed } | Select-Object -ExpandProperty Name | ForEach-Object { Clean-String $_ }} catch {$($_.Exception.Message)}}
    $cpuInfo = @($processors | ForEach-Object {
        @{
            name = Clean-String $_.Name
            number_of_cores = [int]$_.NumberOfCores
            number_of_logical_processors = [int]$_.NumberOfLogicalProcessors
        }
    })
    $macAddresses = $nics | Select-Object -ExpandProperty MACAddress | Where-Object { $_ } | ForEach-Object { Clean-String $_ }
    $ipAddresses = $nics | Select-Object -ExpandProperty IPAddress | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } | ForEach-Object { Clean-String $_ }
    @{
        hostname      =Clean-String $env:COMPUTERNAME
        os_name       =Clean-String $os.Caption
        os_version    =Clean-String $os.Version
        processors    = $cpuInfo
        ram           = [math]::Round($cs.TotalPhysicalMemory / 1MB)
        mac_addresses = $macAddresses
        ip_addresses  = $ipAddresses
        motherboard   = Clean-String "$($baseboard.Manufacturer) $($baseboard.Product)"
        last_boot     = $os.LastBootUpTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
        is_virtual    = $cs.Model -match 'Virtual|VMware|Hyper-V'
        roles         = $roles
    } | ConvertTo-Json -Depth 4 -Compress
} catch {
    @{
        hostname      = Clean-String $env:COMPUTERNAME
        error         = Clean-String $_.Exception.Message
    } | ConvertTo-Json -Compress
}