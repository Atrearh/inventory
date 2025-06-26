$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = $OutputEncoding = [Text.Encoding]::UTF8

function Clean-String($s) {
    if (!$s) { "" }
    else { ($s -replace '[\x00-\x1F\x7F]', '').Trim() -replace '\s+False$', '' }
}

try {
    $softwareList = @()
    foreach ($regPath in "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*") {
        Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | ForEach-Object {
            $name = Clean-String $_.DisplayName
            $installDate = if ($_.InstallDate) { try { [datetime]::ParseExact($_.InstallDate, "yyyyMMdd", $null) } catch { $null } } else { $null }
            if ($name) {
                $softwareList += @{
                    name          = $name
                    version       = Clean-String $_.DisplayVersion
                    install_date  = if ($installDate) { $installDate.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
                    action        = "Installed"
                }
            }
        }
    }
    $softwareList | ConvertTo-Json -Depth 3 -Compress
} catch {
    Write-Error "software_info_full.ps1: $($_.Exception.Message)"
    @() | ConvertTo-Json -Compress
}