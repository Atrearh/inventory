$ErrorActionPreference = "Stop"
#[Console]::OutputEncoding = [Text.Encoding]::UTF8

$f = { if (!$args[0]) { "" } else { ($args[0] -replace '[\x00-\x1F\x7F]', '').Trim() } }

$ld = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 -and $_.Size }
$dd = Get-CimInstance Win32_DiskDrive
$pt = Get-CimInstance Win32_DiskPartition

$r = @()

foreach ($d in $dd) {
    $index = $d.Index
    $partitions = $pt | Where-Object { $_.DiskIndex -eq $index }
    $volumes = @()

    foreach ($p in $partitions) {
        $linked = $ld | Where-Object { $_.VolumeName -and $_.DeviceID -and $_.VolumeSerialNumber -and $_.Size -and $_.FreeSpace -and $_.VolumeName -match '.' -and $_.ProviderName -eq $null -and $_.DriveType -eq 3 }
        $volumes += $linked | Where-Object { $_.DeviceID -eq $p.Name } | ForEach-Object {
            [PSCustomObject]@{
                device_id    = $_.DeviceID
                total_space  = [int64]$_.Size
                free_space   = [int64]$_.FreeSpace
                volume_label = $f.Invoke($_.VolumeName)
            }
        }
    }
    if (-not $volumes) {
        $volumes = $ld | Where-Object { $_.VolumeName -match '.' } | ForEach-Object {
            [PSCustomObject]@{
                device_id    = $_.DeviceID
                total_space  = [int64]$_.Size
                free_space   = [int64]$_.FreeSpace
                volume_label = $f.Invoke($_.VolumeName)
            }
        }
    }
    $mediaType = switch ($d.MediaType) {3 { "HDD" } 4 { "SSD" } default { "Unknown" }}
    $r += [PSCustomObject]@{
        model         = $f.Invoke($d.Model)
        serial        = $f.Invoke($d.SerialNumber)
        interface     = $f.Invoke($d.InterfaceType)
        media_type    = $mediaType
        logical_disks = @($volumes)  # Убедимся, что это массив
    }
}
$r | ConvertTo-Json -Depth 4