param ([Parameter(Mandatory=$true)][string]$ProgramName)
$result = @{ Success = $true; Errors = @(); Data = @{ ProgramName = $ProgramName; Method = "" } }

function Test-AppRemoved {
    param ($AppType, $Name)
    if ($AppType -eq "Win32") {
        $regPaths = @("HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")
        return -not ($regPaths | ForEach-Object { Get-ItemProperty -Path $_ -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "*$Name*" } })
    }
    elseif ($AppType -eq "Win32Product") { return -not (Get-CimInstance -ClassName Win32_Product -Filter "Name like '%$Name%'" -ErrorAction SilentlyContinue) }
}

try {
    $regPaths = @("HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")
    $app = $null
    foreach ($path in $regPaths) {
        $app = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "*$ProgramName*" }
        if ($app) { break }
    }
    if ($app) {
        $uninstallString = $app.UninstallString
        if ($uninstallString -match "msiexec") {
            $msiArgs = ($uninstallString -split "msiexec.exe ")[1] + " /qn"
            Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArgs -Wait -ErrorAction Stop
        } else {
            Start-Process -FilePath "cmd.exe" -ArgumentList "/c $uninstallString /S" -Wait -ErrorAction Stop
        }
        if (Test-AppRemoved -AppType "Win32" -Name $ProgramName) {
            $result.Data.Method = "Registry"
            $result.Data.Message = "Програму '$ProgramName' видалено через реєстр"
        } else {
            throw "Програму '$ProgramName' не вдалося видалити через реєстр"
        }
    }
    else {
        wmic product where "name like '%$ProgramName%'" call uninstall /nointeractive 2>&1 | Out-Null
        if (Test-AppRemoved -AppType "Win32Product" -Name $ProgramName) {
            $result.Data.Method = "WMIC"
            $result.Data.Message = "Програму '$ProgramName' видалено через WMIC"
        }
        else {
            $product = Get-CimInstance -ClassName Win32_Product -Filter "Name like '%$ProgramName%'" -ErrorAction SilentlyContinue
            if ($product) {
                $product | Invoke-CimMethod -MethodName Uninstall -ErrorAction Stop
                if (Test-AppRemoved -AppType "Win32Product" -Name $ProgramName) {
                    $result.Data.Method = "PowerShell"
                    $result.Data.Message = "Програму '$ProgramName' видалено через PowerShell"
                } else {
                    throw "Програму '$ProgramName' не вдалося видалити через PowerShell"
                }
            }
            else {
                throw "Програму '$ProgramName' не знайдено"
            }
        }
    }
}
catch {
    $result.Success = $false
    $result.Errors += $_.Exception.Message
}

ConvertTo-Json -InputObject $result -Compress