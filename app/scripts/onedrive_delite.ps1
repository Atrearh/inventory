$ErrorActionPreference = "SilentlyContinue"
$result = @{ Success = $true; Errors = @() }

try {
    Stop-Process -Name "OneDrive" -Force -ErrorAction SilentlyContinue
    $oneDrivePaths = @("C:\Windows\System32\OneDriveSetup.exe", "C:\Windows\SysWOW64\OneDriveSetup.exe")
    foreach ($path in $oneDrivePaths) {
        if (Test-Path $path) { Start-Process -FilePath $path -ArgumentList "/uninstall" -NoNewWindow -Wait }
    }

    Get-ChildItem 'C:\Users' -Directory | ForEach-Object {
        $paths = @("$($_.FullName)\OneDrive", "$($_.FullName)\AppData\Local\Microsoft\OneDrive", "$($_.FullName)\AppData\Roaming\Microsoft\OneDrive")
        foreach ($p in $paths) { if (Test-Path $p) { Remove-Item -LiteralPath $p -Force -Recurse } }
    }

    @("C:\OneDriveTemp", "C:\ProgramData\Microsoft OneDrive") | ForEach-Object { if (Test-Path $_) { Remove-Item -Path $_ -Recurse -Force } }

    $policyPath = "HKLM:\Software\Policies\Microsoft\Windows\OneDrive"
    if (-not (Test-Path $policyPath)) { New-Item -Path $policyPath -Force | Out-Null }
    Set-ItemProperty -Path $policyPath -Name "DisableFileSyncNGSC" -Value 1 -Force

    @("HKCU:\Software\Microsoft\Windows\CurrentVersion\Run", "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run") | ForEach-Object {
        if (Get-ItemProperty -Path $_ -Name "OneDrive" -ErrorAction SilentlyContinue) { Remove-ItemProperty -Path $_ -Name "OneDrive" }
    }
}
catch {
    $result.Success = $false
    $result.Errors += $_.Exception.Message
}

ConvertTo-Json -InputObject $result -Compress