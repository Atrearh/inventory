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

$seen_disk_numbers = @{}
foreach ($ph in $physical_disks) {
    $serial = Clean $ph.SerialNumber
    if (-not $serial -or $serial -eq "") {$serial = (New-Guid).ToString()}
    $disk_number = $ph.DeviceId
    if ($seen_disk_numbers.ContainsKey($disk_number)) { continue }
    $d = $disks | Where-Object { $_.Number -eq $disk_number } | Select-Object -First 1
    if (-not $d) { continue }
    $mediaType = if ($ph.MediaType -and $ph.MediaType -in @("SSD", "HDD")) {
        $ph.MediaType
    } else {
        if ($d.FriendlyName -like "*SSD*" -or $d.FriendlyName -like "*NVMe*") { "SSD" }
        elseif ($d.FriendlyName -like "*HDD*" -or $d.BusType -eq "SATA" -or $d.BusType -eq "SAS") { "HDD" }
        else { "Unspecified" }
    }
    $result.physical_disks += [PSCustomObject]@{
        model = Clean $ph.FriendlyName
        serial = $serial
        interface = Clean $d.BusType
        media_type = $mediaType
    }
    $seen_disk_numbers[$disk_number] = $true
}
$seen_drive_letters = @{}
foreach ($v in $logical_disks) {
    $drive_letter = $v.DriveLetter
    if (-not $drive_letter -or $seen_drive_letters.ContainsKey($drive_letter)) { continue }
    $p = $partitions | Where-Object { $_.DriveLetter -eq $drive_letter } | Select-Object -First 1
    if (-not $p) { continue }
    $d = $disks | Where-Object { $_.Number -eq $p.DiskNumber } | Select-Object -First 1
    if (-not $d) { continue }
    $ph = $physical_disks | Where-Object { $_.DeviceId -eq $p.DiskNumber } | Select-Object -First 1
    $parent_serial = if ($ph -and $ph.SerialNumber -and $ph.SerialNumber -ne "") {
        Clean $ph.SerialNumber
    } else {(New-Guid).ToString()}
    $result.logical_disks += [PSCustomObject]@{
        device_id = "$($drive_letter):"
        volume_label = Clean $v.FileSystemLabel
        total_space = [int64]$v.Size
        free_space = [int64]$v.SizeRemaining
        serial = Clean $d.SerialNumber
        parent_disk_serial = $parent_serial
    }
    $seen_drive_letters[$drive_letter] = $true
}
$result | ConvertTo-Json -Depth 4