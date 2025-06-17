# software_info.ps1
param($LastUpdated)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
function Clean-String($s) {
    if (!$s) { return "" }
    $s = ($s -replace '[\x00-\x1F\x7F]', '').Trim()
    return ($s -replace '\s+False$', '').Trim()
}
try {
    $softPaths = @(
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $softRaw = foreach ($path in $softPaths) {
        Get-ItemProperty -Path $path -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -and $_.DisplayName.Trim() }
    }
    Write-Debug "Raw software entries: $($softRaw.Count)"
    $softUnique = @{}
    foreach ($s in $softRaw) {
        $n = Clean-String $s.DisplayName
        $installDate = if ($s.InstallDate) {
            try { [datetime]::ParseExact($s.InstallDate, "yyyyMMdd", $null) } catch { $null }
        } else { $null }
        if ($n -and (-not $LastUpdated -or -not $installDate -or $installDate -gt [datetime]::Parse($LastUpdated))) {
            $softUnique[$n] = @{
                DisplayName = $n
                DisplayVersion = Clean-String $s.DisplayVersion
                InstallDate = if ($installDate) { $installDate.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
            }
        }
    }
    Write-Debug "Unique software entries: $($softUnique.Count)"
    $softUnique.Values | ConvertTo-Json -Depth 4 -Compress
} catch {
    Write-Error "Error in software_info.ps1: $($_.Exception.Message)"
    @() | ConvertTo-Json -Compress
}