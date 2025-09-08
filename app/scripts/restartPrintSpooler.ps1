$result = @{ Success = $true; Errors = @() }

try {
    $service = Get-Service -Name Spooler -ErrorAction Stop
    if ($service.Status -eq 'Running') { Stop-Service -Name Spooler -Force -ErrorAction Stop }
    Start-Service -Name Spooler -ErrorAction Stop
    $service = Get-Service -Name Spooler -ErrorAction Stop
    if ($service.Status -ne 'Running') { throw "Служба Spooler не запустилася" }
}
catch {
    $result.Success = $false
    $result.Errors += $_.Exception.Message
}

ConvertTo-Json -InputObject $result -Compress