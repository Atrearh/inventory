# updatePolicies.ps1
# Обновляет групповые политики на удаленном хосте

try {
    # Выполнение команды gpupdate /force
    $result = gpupdate /force
    Write-Output "Групповые политики успешно обновлены: $result"
}
catch {
    Write-Error "Ошибка при обновлении групповых политик: $_"
    exit 1
}