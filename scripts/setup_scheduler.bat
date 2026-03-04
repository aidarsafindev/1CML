@echo off
echo Настройка планировщика Windows для детектора аномалий

:: Путь к Python и скриптам
set PYTHON_PATH=C:\Python39\python.exe
set SCRIPTS_PATH=C:\1CML\scripts

:: Создание задачи для парсера (каждый час)
schtasks /create /tn "1CML Parse TechLog" /tr "%PYTHON_PATH% %SCRIPTS_PATH%\techlog_parser.py --dir C:\1C_techlog" /sc hourly /st 00:05 /f

:: Создание задачи для детектора (каждый час, на 10-й минуте)
schtasks /create /tn "1CML Detect Anomalies" /tr "%PYTHON_PATH% %SCRIPTS_PATH%\detect_anomalies.py" /sc hourly /st 00:10 /f

:: Создание задачи для обучения модели (раз в неделю, воскресенье в 03:00)
schtasks /create /tn "1CML Train Anomaly Model" /tr "%PYTHON_PATH% %SCRIPTS_PATH%\train_anomaly_detector.py --days 30" /sc weekly /d SUN /st 03:00 /f

echo Готово!
pause
