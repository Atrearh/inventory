module.exports = {
  apps: [
    {
      name: 'inventory',
      script: 'C:\\Windows\\System32\\cmd.exe', // Используем cmd.exe для запуска BAT
      args: '/c C:\\Users\\semen\\inv\\start_server.bat', // Выполняем BAT-скрипт
      cwd: 'C:\\Users\\semen\\inv',
      watch: false,
      env: {
        PYTHONPATH: 'C:\\Users\\semen\\inv',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: 'C:\\Users\\semen\\inv\\logs\\pm2-error.log',
      out_file: 'C:\\Users\\semen\\inv\\logs\\pm2-out.log',
      merge_logs: true,
      max_restarts: 10,
      restart_delay: 1000,
      windowsHide: true, // Скрываем консольное окно
      exec_mode: 'fork',
      autorestart: true,
    },
  ],
};