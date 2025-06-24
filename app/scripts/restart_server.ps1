# restart_server.ps1
$ErrorActionPreference = "Stop"
$LogFile = "C:\Users\semen\inv\logs\restart.log"
$BackendDir = "C:\Users\semen\inv"
$FrontendDir = "C:\Users\semen\inv\front"
$BackendPort = 8000
$FrontendPort = 5173

# Функция логирования
function Write-Log {
    param($Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss,fff"
    "$Timestamp $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# Создание директории для логов
$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

# Проверка, запущен ли процесс на указанном порту
function Test-Port {
    param($Port)
    $Connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $Connection
}

# Проверка и запуск бэкенда
Write-Log "Проверка статуса бэкенда на порту $BackendPort"
if (-not (Test-Port -Port $BackendPort)) {
    Write-Log "Бэкенд не запущен, запускаем..."
    try {
        $BackendLog = "$BackendDir\logs\uvicorn.log"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c python -m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort > $BackendLog 2>&1" -WorkingDirectory $BackendDir -NoNewWindow
        Write-Log "Бэкенд запущен"
    } catch {
        Write-Log "Ошибка запуска бэкенда: $_"
        exit 1
    }
} else {
    Write-Log "Бэкенд уже запущен на порту $BackendPort"
}

# Проверка и запуск фронтенда
Write-Log "Проверка статуса фронтенда на порту $FrontendPort"
if (-not (Test-Port -Port $FrontendPort)) {
    Write-Log "Фронтенд не запущен, запускаем..."
    try {
        $FrontendLog = "$FrontendDir\logs\vite.log"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev > $FrontendLog 2>&1" -WorkingDirectory $FrontendDir -NoNewWindow
        Write-Log "Фронтенд запущен"
    } catch {
        Write-Log "Ошибка запуска фронтенда: $_"
        exit 1
    }
} else {
    Write-Log "Фронтенд уже запущен на порту $FrontendPort"
}