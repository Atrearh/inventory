$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = $OutputEncoding = [Text.Encoding]::UTF8

function Clean-String($s) {
    if (!$s) { "" }
    else { ($s -replace '[^\x20-\x7E]', '').Trim() -replace '\s+False$', '' }
}

try {
    $softwareList = [System.Collections.Generic.List[PSObject]]::new()
    foreach ($regPath in "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*") {
        Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | ForEach-Object {
            $name = Clean-String $_.DisplayName
            $installDate = if ($_.InstallDate -and $_.InstallDate -match '^\d{8}$') { 
                try { [datetime]::ParseExact($_.InstallDate, "yyyyMMdd", $null) } catch { $null } 
            } else { $null }
            if ($name) {
                $softwareList.Add([PSCustomObject]@{
                    name          = $name
                    version       = Clean-String $_.DisplayVersion
                    publisher     = Clean-String $_.Publisher
                    install_date  = if ($installDate) { $installDate.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
                    action        = "Installed"
                })
            }
        }
    }
    $softwareList = $softwareList | Where-Object {
        ($_.publisher -ne "Microsoft Corporation") -or
        ($_.name -notmatch "Update|Security|Office|Hotfix|KB\d{7}")
    }
    $softwareList | ConvertTo-Json -Depth 3 -Compress
} catch {
    Write-Error "software_info_full.ps1: $($_.Exception.Message)"
    @() | ConvertTo-Json -Compress
}