try {
    # Виконуємо команду gpupdate.exe та захоплюємо весь вивід (stdout + stderr)
    $result = gpupdate.exe 2>&1

    # Формуємо JSON-об’єкт для успішного виконання
    $output = @{
        stdout = "Групові політики успішно оновлено:`n" + ($result -join "`n")
        stderr = ""
    }

    # Конвертуємо в JSON
    $output | ConvertTo-Json -Compress
}
catch {
    # Формуємо JSON-об’єкт для помилки
    $output = @{
        stdout = ""
        stderr = "Помилка при оновленні групових політик: $_"
    }

    # Конвертуємо в JSON
    $output | ConvertTo-Json -Compress

    # Виходимо з кодом помилки
    exit 1
}
