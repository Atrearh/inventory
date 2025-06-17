# software_info.ps1
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("Full", "Changes")]
    [string]$Mode = "Full",
    [Parameter(Mandatory=$false)]
    [string]$LastUpdated
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Clean-String {
    param([string]$s)
    if ([string]::IsNullOrEmpty($s)) { return "" }
    ($s -replace '[\x00-\x1F\x7F]', '').Trim() -replace '\s+False$', ''
}

function Get-SoftwareRegistry {
    $softPaths = @(
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $softRaw = $softPaths | ForEach-Object {
        Get-ItemProperty -Path $_ -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -and $_.DisplayName.Trim() }
    }
    Write-Debug "Raw software entries: $($softRaw.Count)"
    $softUnique = @{}
    foreach ($s in $softRaw) {
        $name = Clean-String $s.DisplayName
        if ([string]::IsNullOrEmpty($name)) { continue }
        $installDate = if ($s.InstallDate) {
            try { [datetime]::ParseExact($s.InstallDate, "yyyyMMdd", $null) } catch { $null }
        } else { $null }
        if (-not $LastUpdated -or -not $installDate -or $installDate -gt [datetime]::Parse($LastUpdated)) {
            $softUnique[$name] = @{
                DisplayName = $name
                DisplayVersion = Clean-String $s.DisplayVersion
                InstallDate = if ($installDate) { $installDate.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { $null }
            }
        }
    }
    Write-Debug "Unique software entries: $($softUnique.Count)"
    return $softUnique
}

function Get-SoftwareChanges {
    param([string]$LastUpdated)
    $changes = @()
    $afterTime = if ($LastUpdated) { [datetime]::Parse($LastUpdated) } else { (Get-Date).AddDays(-1) }
    $events = Get-WinEvent -FilterHashtable @{
        LogName = "Application"
        Id = 102, 103, 11707, 11724
        StartTime = $afterTime
    } -ErrorAction SilentlyContinue
    foreach ($event in $events) {
        $name = $event.Properties[0].Value
        $version = $event.Properties[1].Value
        $action = switch ($event.Id) {
            102 { "Installed" }
            103 { "Uninstalled" }
            11707 { "Installed" }
            11724 { "Uninstalled" }
        }
        if ($name) {
            $changes += @{
                DisplayName = Clean-String $name
                DisplayVersion = Clean-String $version
                Action = $action
                EventTime = $event.TimeCreated.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss")
            }
        }
    }
    Write-Debug "Detected software changes: $($changes.Count)"
    return $changes
}

try {
    switch ($Mode) {
        "Full" {
            $software = Get-SoftwareRegistry
            $software.Values | ConvertTo-Json -Depth 4 -Compress
        }
        "Changes" {
            $changes = Get-SoftwareChanges -LastUpdated $LastUpdated
            $changes | ConvertTo-Json -Depth 4 -Compress
        }
    }
} catch {
    Write-Error "Error in software_info.ps1: $($_.Exception.Message)"
    @() | ConvertTo-Json -Compress
}