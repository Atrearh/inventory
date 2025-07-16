# Вимикаємо помилки
$ErrorActionPreference = "SilentlyContinue"

# 1. Зупинити процеси OneDrive
Write-Host "Stopping OneDrive..."
Stop-Process -Name "OneDrive" -Force -ErrorAction SilentlyContinue

# 2. Видалити сам застосунок OneDrive (x64 та x86)
Write-Host "Uninstalling OneDrive..."
Start-Process -FilePath "C:\Windows\System32\OneDriveSetup.exe" -ArgumentList "/uninstall" -NoNewWindow -Wait
Start-Process -FilePath "C:\Windows\SysWOW64\OneDriveSetup.exe" -ArgumentList "/uninstall" -NoNewWindow -Wait

# 3. Видалити залишки в профілях користувачів
Write-Host "Removing OneDrive folders from user profiles..."
Get-ChildItem 'C:\Users' -Directory | ForEach-Object {
    $userProfile = $_.FullName
    Remove-Item -LiteralPath "$userProfile\OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$userProfile\AppData\Local\Microsoft\OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$userProfile\AppData\Roaming\Microsoft\OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$userProfile\AppData\Local\OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
}

# 4. Очистити загальні папки OneDrive
Write-Host "Removing global OneDrive folders..."
Remove-Item -Path "C:\OneDriveTemp" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "C:\ProgramData\Microsoft OneDrive" -Recurse -Force -ErrorAction SilentlyContinue

# 5. Видалити залишки в реєстрі (автозапуск)
Write-Host "Cleaning OneDrive registry entries..."
Remove-ItemProperty -Path "HKLM:\Software\Policies\Microsoft\Windows\OneDrive" -Name "DisableFileSyncNGSC" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKLM:\Software\Policies\Microsoft\Windows\OneDrive" -Name "DisableFileSyncNGSC" -Value 1 -Force

# 6. Очистити OneDrive із автозапуску (на всякий випадок)
Write-Host "Disabling OneDrive autorun..."
$runKeys = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
)
foreach ($key in $runKeys) {
    Remove-ItemProperty -Path $key -Name "OneDrive" -ErrorAction SilentlyContinue
}

Write-Host "`n✅ OneDrive has been removed and cleaned from all users."
