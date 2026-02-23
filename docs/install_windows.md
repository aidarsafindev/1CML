# Установка и настройка на Windows 10

Полное руководство по развертыванию системы прогнозирования для 1С на Windows 10.

## 📋 Предварительные требования

- Windows 10 Pro/Enterprise (x64)
- 8+ ГБ RAM (рекомендуется 16 ГБ)
- 20+ ГБ свободного места
- Права администратора
- Установленный Git

## 🚀 Пошаговая установка

### Шаг 1. Подготовка окружения

```powershell
# Создаем рабочую директорию
mkdir C:\1CML
cd C:\1CML

# Клонируем репозиторий
git clone https://github.com/aidarsafindev/1CML.git .

Шаг 2. Установка Python
Скачайте Python 3.10+ с python.org

При установке обязательно отметьте "Add Python to PATH"

Проверьте установку:
python --version
pip --version

Шаг 3. Установка зависимостей
cd C:\1CML
pip install -r requirements.txt

Шаг 4. Установка Docker Desktop
Скачайте Docker Desktop с docker.com

Установите, перезагрузите компьютер

Запустите Docker Desktop

Шаг 5. Запуск ClickHouse
# Запускаем ClickHouse в контейнере
docker run -d `
  --name clickhouse-server `
  -p 8123:8123 `
  -p 9000:9000 `
  -v C:/1CML/clickhouse/data:/var/lib/clickhouse `
  -v C:/1CML/clickhouse/logs:/var/log/clickhouse-server `
  clickhouse/clickhouse-server

# Проверяем работу
curl http://localhost:8123/ping
# Должен вернуть Ok.

Шаг 6. Установка PostgreSQL
# Запускаем PostgreSQL в Docker
docker run -d `
  --name postgres `
  -p 5432:5432 `
  -e POSTGRES_PASSWORD=password `
  -e POSTGRES_DB=monitoring `
  -v C:/1CML/postgresql/data:/var/lib/postgresql/data `
  postgres:14

# Создаем таблицы
docker exec -i postgres psql -U postgres -d monitoring < C:\1CML\postgresql\create_tables.sql

Шаг 7. Установка Prometheus

# Скачиваем Prometheus
cd C:\1CML
curl -L -o prometheus.zip https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.windows-amd64.zip
tar -xf prometheus.zip
move prometheus-* prometheus

# Копируем конфиг
copy C:\1CML\prometheus\prometheus.yml C:\1CML\prometheus\
copy C:\1CML\prometheus\alerts.yml C:\1CML\prometheus\

# Запускаем Prometheus
cd C:\1CML\prometheus
start /B prometheus.exe --config.file=prometheus.yml

Шаг 8. Установка Windows Exporter

# Скачиваем Windows Exporter
cd C:\1CML
curl -L -o windows_exporter.exe https://github.com/prometheus-community/windows_exporter/releases/download/v0.24.0/windows_exporter-0.24.0-amd64.exe

# Устанавливаем как сервис
.\windows_exporter.exe install

# Запускаем сервис
net start windows_exporter

Шаг 9. Установка Grafana

# Скачиваем Grafana
cd C:\1CML
curl -L -o grafana.msi https://dl.grafana.com/enterprise/release/grafana-enterprise-10.2.2.windows-amd64.msi

# Устанавливаем
msiexec /i grafana.msi /quiet

# Запускаем Grafana
net start grafana

Шаг 10. Настройка Grafana
Откройте браузер: http://localhost:3000

Логин: admin, пароль: admin (смените при первом входе)

Добавьте источники данных:

Configuration → Data Sources → Add data source

Prometheus: http://localhost:9090

PostgreSQL: настройте как в datasources.yml

ClickHouse: установите плагин и настройте

Импортируйте дашборды:

Create → Import

Загрузите JSON-файлы из C:\1CML\grafana\dashboards\

Шаг 11. Настройка Telegram-уведомлений
Создайте бота в Telegram через @BotFather

Получите токен

Создайте группу и добавьте бота

Получите Chat ID (можно через @userinfobot)

Отредактируйте .env файл:
copy C:\1CML\.env.example C:\1CML\.env
notepad C:\1CML\.env
# Заполните TELEGRAM_TOKEN и TELEGRAM_CHAT_ID

Шаг 12. Тестовый запуск прогноза
cd C:\1CML
python scripts\predict_disk.py --source test

Шаг 13. Настройка автоматического запуска
Вариант А: Планировщик задач Windows

Запустите taskschd.msc

Create Basic Task

Имя: "1CML Disk Predict"

Триггер: Ежедневно в 08:00

Действие: Запуск программы

Program: C:\Python310\python.exe

Arguments: C:\1CML\scripts\predict_disk.py

Start in: C:\1CML

Вариант Б: Создание службы (для продвинутых)
# Установите NSSM (Non-Sucking Service Manager)
choco install nssm

# Создайте службу для Python-скрипта
nssm install 1CML_Predict C:\Python310\python.exe C:\1CML\scripts\predict_disk.py
nssm set 1CML_Predict Start SERVICE_AUTO_START
nssm start 1CML_Predict

🔧 Проверка работоспособности
Проверка 1: Все сервисы запущены

# Проверяем Docker контейнеры
docker ps

# Проверяем службы Windows
Get-Service prometheus, windows_exporter, grafana

Проверка 2: Доступность эндпоинтов

curl http://localhost:9090           # Prometheus
curl http://localhost:9182/metrics    # Windows Exporter
curl http://localhost:3000            # Grafana
curl http://localhost:8123/play       # ClickHouse

Проверка 3: Работа прогноза

# Запускаем с тестовыми данными
python scripts\predict_disk.py --source test

# Проверяем лог
type logs\disk_predict.log

Проверка 4: Данные в БД

# Подключаемся к PostgreSQL
docker exec -it postgres psql -U postgres -d monitoring

# Проверяем прогнозы
SELECT * FROM disk_forecast ORDER BY metric_date DESC LIMIT 5;

# Выход
\q

Решение проблем
Проблема: Не запускается ClickHouse

# Проверьте, не занят ли порт
netstat -ano | findstr :8123

# Перезапустите контейнер
docker restart clickhouse-server

Проблема: Нет данных в Prometheus

# Проверьте конфиг
type C:\1CML\prometheus\prometheus.yml

# Проверьте таргеты
# Откройте http://localhost:9090/targets

Проблема: Python не видит модули

# Переустановите зависимости
pip uninstall -r requirements.txt -y
pip install -r requirements.txt

Проблема: Ошибки прав доступа

# Запустите PowerShell от администратора
# Дайте права на выполнение скриптов
Set-ExecutionPolicy RemoteSigned

Следующие шаги
Настройка сбора техжурнала 1С

Отредактируйте scripts/techlog_parser.py

Укажите путь к техжурналу

Обучение модели аномалий

python scripts\train_anomaly_detector.py --days 30

3. Интеграция с 1С

Настройте выгрузку данных через HTTP-сервисы

Или используйте прямое подключение к БД

4. Кастомизация дашбордов

Отредактируйте JSON-файлы в grafana/dashboards/

Создайте свои графики
