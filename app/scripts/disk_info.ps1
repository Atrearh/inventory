$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Clean($v) {
    if (-not $v) { return "" }
    return ($v -replace '[\x00-\x1F\x7F]', '').Trim() -replace '\.$|^\s+|\s+$', ''
}
$physical_disks = Get-PhysicalDisk
$logical_disks = Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.Size -gt 0 }
$partitions = Get-Partition | Where-Object { $_.DriveLetter }
$disks = Get-Disk
$result = @{
    physical_disks = @() 
    logical_disks = @()
}

foreach ($ph in $physical_disks) {
    $d = $disks | Where-Object { $_.FriendlyName -eq $ph.FriendlyName -or ($_.SerialNumber -and (Clean $_.SerialNumber -eq Clean $ph.SerialNumber)) } | Select-Object -First 1
    $mediaType = if ($ph.MediaType -and $ph.MediaType -in @("SSD", "HDD")) {
        $ph.MediaType
    } else {
        if ($d.FriendlyName -like "*SSD*" -or $d.FriendlyName -like "*NVMe*") { "SSD" }
        elseif ($d.FriendlyName -like "*HDD*" -or $d.BusType -eq "SATA" -or $d.BusType -eq "SAS") { "HDD" }
        else { "Unspecified" }
    }
    $result.physical_disks += [PSCustomObject]@{
        model = Clean $ph.FriendlyName
        serial = Clean $ph.SerialNumber
        interface = Clean $d.BusType
        media_type = $mediaType
    }
}
foreach ($v in $logical_disks) {
    $p = $partitions | Where-Object { $_.DriveLetter -eq $v.DriveLetter }
    if (-not $p) { continue }

    $d = $disks | Where-Object { $_.Number -eq $p.DiskNumber }
    $ph = $physical_disks | Where-Object { $_.FriendlyName -eq $d.FriendlyName -or ($_.SerialNumber -and (Clean $_.SerialNumber -eq Clean $d.SerialNumber)) } | Select-Object -First 1

    $result.logical_disks += [PSCustomObject]@{
        device_id = "$($v.DriveLetter):"
        volume_label = Clean $v.FileSystemLabel
        total_space = [int64]$v.Size
        free_space = [int64]$v.SizeRemaining
        serial = Clean $d.SerialNumber 
    }
}
$result | ConvertTo-Json -Depth 4