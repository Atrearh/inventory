$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function Clean($v) {
    if (-not $v) { return "" }
    return ($v -replace '[\x00-\x1F\x7F]', '').Trim() -replace '\.$|^\s+|\s+$', ''
}

$volumes = Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.Size -gt 0 }
$partitions = Get-Partition | Where-Object { $_.DriveLetter }
$disks = Get-Disk
$physDisks = Get-PhysicalDisk

$results = foreach ($v in $volumes) {
    $p = $partitions | Where-Object { $_.DriveLetter -eq $v.DriveLetter }
    if (-not $p) { continue }

    $d = $disks | Where-Object { $_.Number -eq $p.DiskNumber }
    $ph = $physDisks | Where-Object { $_.FriendlyName -eq $d.FriendlyName -or ($_.SerialNumber -and (Clean $_.SerialNumber -eq Clean $d.SerialNumber)) } | Select-Object -First 1

    $mediaType = if ($ph -and $ph.MediaType -and $ph.MediaType -in @("SSD", "HDD")) {
        $ph.MediaType
    } else {
        if ($d.FriendlyName -like "*SSD*" -or $d.FriendlyName -like "*NVMe*") { "SSD" }
        elseif ($d.FriendlyName -like "*HDD*" -or $d.BusType -eq "SATA" -or $d.BusType -eq "SAS") { "HDD" }
        else { "Unspecified" }
    }

    [PSCustomObject]@{
        device_id    = "$($v.DriveLetter):"
        total_space  = [int64]$v.Size
        free_space   = [int64]$v.SizeRemaining
        volume_label = Clean $v.FileSystemLabel
        model        = Clean $d.FriendlyName
        serial       = Clean $d.SerialNumber
        interface    = Clean $d.BusType
        media_type   = $mediaType
    }
}

if ($results -is [array]) {
    $results | ConvertTo-Json -Depth 4
} else {
    ,$results | ConvertTo-Json -Depth 4
}
