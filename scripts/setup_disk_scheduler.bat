@echo off
echo Настройка планировщика для прогноза диска

:: Путь к Python и скриптам
set PYTHON_PATH=C:\Python39\python.exe
set SCRIPTS_PATH=C:\1CML\scripts

:: Сбор метрик (каждый час)
schtasks /create /tn "1CML Collect Disk Metrics" /tr "%PYTHON_PATH% %SCRIPTS_PATH%\collect_disk_metrics.py" /sc hourly /st 00:01 /f

:: Прогноз для всех дисков (каждый день в 08:00)
schtasks /create /tn "1CML Predict Disks" /tr "%PYTHON_PATH% %SCRIPTS_PATH%\check_all_disks.py" /sc daily /st 08:00 /f

:: Очистка старых данных (1-го числа каждого месяца)
schtasks /create /tn "1CML Cleanup Old Data" /tr "%PYTHON_PATH% %SCRIPTS_PATH%\cleanup_old_data.py" /sc monthly /d 1 /st 03:00 /f

echo Готово!
pause
