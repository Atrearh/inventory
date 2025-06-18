param(
    [string]$LastUpdated = "None"
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = $OutputEncoding = [Text.Encoding]::UTF8

function Clean-String($s) {
    if (!$s) { "" }
    else { ($s -replace '[\x00-\x1F\x7F]', '').Trim() -replace '\s+False$', '' }
}

try {
    $softwareList = @{}
    foreach ($regPath in "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*") {
        Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | ForEach-Object {
            $name = Clean-String $_.DisplayName
            $installDate = if ($_.InstallDate) { try { [datetime]::ParseExact($_.InstallDate, "yyyyMMdd", $null) } catch { $null } } else { $null }
            if ($name) {
                $softwareList[$name] = @{
                    DisplayName   = $name
                    DisplayVersion = Clean-String $_.DisplayVersion
                    InstallDate   = if ($installDate) { $installDate.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
                }
            }
        }
    }

    if ($LastUpdated -ne "None") {
        $lastUpdatedDate = [datetime]::Parse($LastUpdated).ToUniversalTime()
        $filteredSoftware = @{}
        try {
            $events = Get-WinEvent -LogName "System" -ErrorAction SilentlyContinue | Where-Object {
                ($_.Id -eq 11707 -or $_.Id -eq 1033) -and $_.TimeCreated -gt $lastUpdatedDate
            }
            foreach ($event in $events) {
                $appName = $event.Properties[0].Value
                if ($softwareList.ContainsKey($appName)) {
                    $filteredSoftware[$appName] = $softwareList[$appName]
                    $filteredSoftware[$appName].InstallDate = $event.TimeCreated.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
                }
            }
        } catch {
            Write-Warning "Ошибка доступа к журналу событий: $($_.Exception.Message), использую данные реестра"
            foreach ($name in $softwareList.Keys) {
                $installDate = $softwareList[$name].InstallDate
                if ($installDate -and [datetime]::Parse($installDate) -gt $lastUpdatedDate) {
                    $filteredSoftware[$name] = $softwareList[$name]
                }
            }
        }
        $filteredSoftware.Values | ConvertTo-Json -Depth 3 -Compress
    } else {
        @() | ConvertTo-Json -Compress
    }
} catch {
    Write-Error "software_info_changes.ps1: $($_.Exception.Message)"
    @() | ConvertTo-Json -Compress
}