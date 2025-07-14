# restartPrintSpooler.ps1
# Перезапускает службу печати (Spooler) на удаленном хосте

try {
    # Проверка состояния службы Spooler
    $service = Get-Service -Name Spooler -ErrorAction Stop
    if ($service.Status -eq 'Running') {
        # Остановка службы
        Stop-Service -Name Spooler -Force -ErrorAction Stop
        Start-Sleep -Seconds 2  # Пауза для завершения остановки
    }
    
    # Запуск службы
    Start-Service -Name Spooler -ErrorAction Stop
    Write-Output "Диспетчер печати успешно перезапущен"
}
catch {
    Write-Error "Ошибка при перезапуске службы Spooler: $_"
    exit 1
}