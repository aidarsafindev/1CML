# 1CML — Machine Learning для 1С

**Превентивная аналитика и прогнозирование сбоев в 1С с помощью Open Source инструментов.**

> ⚠️ **Статус проекта**: Это концепт, эксперимент, первые шаги. Репозиторий создан для демонстрации подхода, набора идей и работающих прототипов. В промышленную эксплуатацию пока не внедрено, но вы можете забрать себе полезные куски и доработать под свои задачи.

---

## 📋 Содержание
- [Возможности](#-возможности)
- [Быстрый старт за 15 минут](#-быстрый-старт-за-15-минут)
- [Архитектура решения](#-архитектура-решения)
- [Структура репозитория](#-структура-репозитория)
- [Компоненты](#-компоненты)
  - [Источники данных](#-источники-данных)
  - [ClickHouse: хранение техжурнала](#-clickhouse-хранение-техжурнала)
  - [PostgreSQL: хранение результатов](#-postgresql-хранение-результатов)
  - [Prometheus: сбор метрик](#-prometheus-сбор-метрик)
  - [Grafana: дашборды](#-grafana-дашборды)
- [Модули прогнозирования](#-модули-прогнозирования)
  - [Прогноз диска](#-прогноз-диска)
  - [Детектор аномалий](#-детектор-аномалий)
  - [Прогноз дедлоков](#-прогноз-дедлоков)
- [ITSM-интеграция](#-itsm-интеграция)
- [ML для чайников](#-ml-для-чайников)
- [Результаты пилотного внедрения](#-результаты-пилотного-внедрения)
- [Roadmap](#-roadmap)
- [FAQ](#-faq)
- [Контакты](#-контакты)
- [Лицензия](#-лицензия)

---

## 🚀 Возможности

| Модуль | Что делает | Технологии | Статус |
|--------|------------|-------------|--------|
| **📀 Прогноз диска** | Предсказывает дату заполнения диска с точностью до дня | Linear Regression, Prophet | ✅ Работает |
| **🔒 Прогноз дедлоков** | Анализирует тренды блокировок и предупреждает о риске дедлоков | Time Series Analysis, ClickHouse | ✅ Работает |
| **📊 Детектор аномалий** | Выявляет аномалии в активности пользователей | Isolation Forest, 3-Sigma | ✅ Работает |
| **🤖 ML-модели** | Классифицирует предсбойные состояния | Random Forest, SVM | 🚧 В разработке |
| **📈 Дашборды** | Визуализирует тренды и прогнозы | Grafana | ✅ Готово |
| **🔔 Алерты** | Отправляет уведомления в Telegram | Alertmanager, Webhooks | ✅ Готово |
| **📋 ITSM-интеграция** | Автоматически создает задачи в Jira/YouTrack/ServiceNow | REST API | ✅ Готово |
| **📦 Сбор данных** | Парсит техжурнал 1С в ClickHouse | Python, ClickHouse | ✅ Готово |

---

## ⚡ Быстрый старт за 15 минут

```bash
# 1. Клонируем репозиторий
git clone https://github.com/aidarsafindev/1CML.git
cd 1CML

# 2. Запускаем ClickHouse в Docker
docker run -d -p 8123:8123 -p 9000:9000 --name clickhouse-server clickhouse/clickhouse-server

# 3. Создаем таблицы в ClickHouse
cat clickhouse/schema.sql | docker exec -i clickhouse-server clickhouse-client --multiline
cat clickhouse/schema_locks.sql | docker exec -i clickhouse-server clickhouse-client --multiline

# 4. Устанавливаем зависимости Python
pip install -r requirements.txt

# 5. Копируем и настраиваем .env
cp .env.example .env
# отредактируйте .env под свои параметры

# 6. Создаем таблицы в PostgreSQL
# (если PostgreSQL запущен в Docker)
docker exec -i postgres psql -U postgres -d monitoring < postgresql/create_tables.sql

# 7. Запускаем тестовый прогноз диска
python scripts/predict_disk.py --disk D: --test

# 8. Импортируем дашборды в Grafana
# Grafana → Import → /grafana/dashboards/disk_forecast.json
```

**Подробная инструкция для Windows 10:** [docs/install_windows.md](docs/install_windows.md)

---

## 🏗 Архитектура решения

```
┌─────────────────┐    ┌─────────────────┐     ┌─────────────────┐
│   Техжурнал 1С  │───▶│    ClickHouse   │───▶│                 │
│  (блокировки)   │    │ (lock_events)   │     │                 │
└─────────────────┘    └─────────────────┘     │                 │
                                               │     Grafana     │
┌─────────────────┐    ┌─────────────────┐     │   (визуализация │
│ Метрики Windows │───▶│    Prometheus   │───▶│    + прогноз)   │
│  (диск, CPU)    │    └─────────────────┘     │                 │
└─────────────────┘              │             └─────────────────┘
                                 ▼                      ▲
                          ┌─────────────┐               │
                          │  PostgreSQL │───────────────┘
                          │ (прогнозы)  │
                          └─────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
            ┌─────────────┐           ┌─────────────┐
            │  Telegram   │           │Jira/YouTrack│
            │   Алерты    │           │   Задачи    │
            └─────────────┘           └─────────────┘
```

---

## 📁 Структура репозитория

```
1CML/
│
├── 📁 prometheus/               # Конфигурация Prometheus
│   ├── prometheus.yml           # Основной конфиг с job'ами
│   ├── alerts.yml               # Правила алертов
│   └── alertmanager.yml         # Настройка вебхуков в ITSM
│
├── 📁 grafana/                   # Дашборды и источники данных
│   ├── datasources.yml          # Настройка источников
│   └── 📁 dashboards/            # JSON-дашборды
│       ├── disk_forecast.json   # Прогноз диска
│       ├── locks_trend.json     # Тренды блокировок
│       └── anomalies.json       # Контрольные карты
│
├── 📁 clickhouse/                 # Схемы для ClickHouse
│   ├── schema.sql                # Основные таблицы для техжурнала
│   ├── schema_locks.sql          # Таблицы для анализа блокировок
│   └── queries.sql               # Полезные запросы
│
├── 📁 postgresql/                 # Схемы для PostgreSQL
│   └── create_tables.sql         # Таблицы для прогнозов
│
├── 📁 scripts/                    # Python-скрипты
│   │
│   ├── 📁 disk/                   # Прогноз диска
│   │   ├── collect_disk_metrics.py    # Сбор метрик диска
│   │   ├── predict_disk.py            # Основной скрипт прогноза
│   │   ├── check_all_disks.py         # Проверка всех дисков
│   │   └── cleanup_old_data.py        # Очистка старых данных
│   │
│   ├── 📁 locks/                   # Прогноз дедлоков
│   │   ├── techlog_parser_locks.py    # Парсер блокировок
│   │   ├── analyze_lock_trends.py     # Анализ трендов
│   │   └── check_deadlocks.py         # Основной скрипт проверки
│   │
│   ├── 📁 anomalies/                # Детектор аномалий
│   │   ├── prepare_training_data.py    # Подготовка данных
│   │   ├── train_anomaly_detector.py   # Обучение модели
│   │   ├── get_current_metrics.py      # Получение текущих метрик
│   │   └── detect_anomalies.py         # Детектор аномалий
│   │
│   ├── 📁 itsm/                     # ITSM-интеграции
│   │   ├── base.py                     # Базовый класс
│   │   ├── factory.py                  # Фабрика клиентов
│   │   ├── jira_integration.py         # Jira Cloud/Server
│   │   ├── youtrack_integration.py     # YouTrack
│   │   ├── servicenow_integration.py   # ServiceNow
│   │   ├── redmine_integration.py      # Redmine
│   │   ├── gitlab_integration.py       # GitLab Issues
│   │   ├── test_create.py              # Тестовое создание
│   │   └── check_config.py             # Проверка настроек
│   │
│   ├── alert_telegram.py           # Отправка алертов в Telegram
│   └── webhook_handler.py          # Вебхук от Alertmanager
│
├── 📁 docs/                       # Документация
│   ├── install_windows.md         # Инструкция для Windows 10
│   ├── ml_for_dummies.md          # ML для начинающих
│   └── itsm.md                    # Документация по ITSM
│
├── 📁 tests/                      # Тесты
│   └── test_predict.py
│
├── 📁 models/                     # Сохраненные ML-модели
│   └── .gitkeep
│
├── 📁 logs/                       # Логи работы скриптов
│   └── .gitkeep
│
├── docker-compose.itsm.yml       # Docker-стек для ITSM
├── Dockerfile.webhook            # Docker-образ для вебхука
├── .env.example                   # Пример переменных окружения
├── .gitignore                     # Игнорируемые файлы
├── requirements.txt               # Зависимости Python
├── LICENSE                        # MIT License
└── README.md                      # Этот файл
```

---

## 🔧 Компоненты

### 📊 Источники данных

| Источник | Что собираем | Куда сохраняем |
|----------|--------------|----------------|
| Техжурнал 1С (LOCK, DEADLOCK) | Блокировки, дедлоки, таймауты | ClickHouse (`lock_events`) |
| Техжурнал 1С (SESSION) | Сессии пользователей | ClickHouse (`session_events`) |
| Windows Performance Counters | Метрики диска, CPU, памяти | Prometheus → PostgreSQL |
| PostgreSQL | Статистика СУБД | Prometheus |

### 🗄️ ClickHouse: хранение техжурнала

**Файлы:**
- [`clickhouse/schema.sql`](clickhouse/schema.sql) — основные таблицы
- [`clickhouse/schema_locks.sql`](clickhouse/schema_locks.sql) — таблицы для блокировок
- [`clickhouse/queries.sql`](clickhouse/queries.sql) — полезные запросы

**Основные таблицы:**
- `lock_events` — сырые события блокировок
- `lock_hourly_stats` — агрегация по часам
- `lock_table_stats` — статистика по таблицам
- `session_events` — события сессий

**Пример запроса:**
```sql
-- Топ-10 таблиц по блокировкам за сегодня
SELECT 
    table_name,
    count() as locks,
    countIf(event_type = 'DEADLOCK') as deadlocks,
    avg(lock_wait_time)/1000 as avg_wait_ms
FROM lock_events
WHERE event_date = today() AND table_name != ''
GROUP BY table_name
ORDER BY locks DESC
LIMIT 10;
```

### 🐘 PostgreSQL: хранение результатов

**Файл:** [`postgresql/create_tables.sql`](postgresql/create_tables.sql)

**Основные таблицы:**
- `disk_usage` — история заполнения дисков
- `disk_forecast` — прогнозы по дискам
- `disk_alerts` — история алертов
- `anomaly_checks` — результаты проверки аномалий
- `deadlock_checks` — результаты проверки дедлоков
- `model_quality` — метрики качества моделей

### 📈 Prometheus: сбор метрик

**Файлы:**
- [`prometheus/prometheus.yml`](prometheus/prometheus.yml) — основной конфиг
- [`prometheus/alerts.yml`](prometheus/alerts.yml) — правила алертов
- [`prometheus/alertmanager.yml`](prometheus/alertmanager.yml) — настройка вебхуков

**Метрики:**
- `windows_logical_disk_used_bytes` — занятое место на диске
- `windows_logical_disk_free_bytes` — свободное место
- `windows_cpu_usage_total` — загрузка CPU
- `windows_memory_available_bytes` — доступная память

### 📊 Grafana: дашборды

**Файлы в [`grafana/dashboards/`](grafana/dashboards/):**

| Дашборд | Файл | Назначение |
|---------|------|------------|
| Прогноз диска | `disk_forecast.json` | Факт + прогноз + пороги |
| Тренды блокировок | `locks_trend.json` | Анализ LockTime |
| Контрольные карты | `anomalies.json` | Выявление аномалий |

---

## 🤖 Модули прогнозирования

### 📀 Прогноз диска

**Файлы:** [`scripts/disk/`](scripts/disk/)

**Что делает:**
- Собирает метрики диска каждый час
- Обучает линейную регрессию на 60 днях истории
- Прогнозирует заполнение на 7, 14, 30 дней
- Рассчитывает дни до достижения лимита
- Отправляет алерты при риске

**Запуск:**
```bash
# Сбор метрик (каждый час)
python scripts/disk/collect_disk_metrics.py

# Прогноз для диска D:
python scripts/disk/predict_disk.py --disk D:

# Прогноз для всех дисков
python scripts/disk/check_all_disks.py

# Тестовый прогноз
python scripts/disk/predict_disk.py --disk D: --test
```

**Пример результата:**
```
📊 Диск D: - 156.3 ГБ, скорость роста 2.8 ГБ/день
🔮 Прогноз через 14 дней: 195.1 ГБ
⚠️ Дней до лимита: 16
```

### 🔒 Прогноз дедлоков

**Файлы:** [`scripts/locks/`](scripts/locks/)

**Что делает:**
- Парсит техжурнал 1С в ClickHouse каждый час
- Анализирует тренды блокировок
- Обнаруживает рост времени ожидания
- Предупреждает о риске дедлоков

**Запуск:**
```bash
# Парсинг техжурнала
python scripts/locks/techlog_parser_locks.py --dir C:\1C_techlog

# Анализ трендов
python scripts/locks/analyze_lock_trends.py

# Проверка риска дедлоков (каждый час)
python scripts/locks/check_deadlocks.py
```

**Пример результата:**
```
🔒 АНАЛИЗ БЛОКИРОВОК
📈 Рост времени ожидания: +140% за неделю
🚨 Обнаружены deadlock'и: 3 за последний час
📋 Топ таблиц: _InfoRg12345 (245 блокировок)
```

### 📊 Детектор аномалий

**Файлы:** [`scripts/anomalies/`](scripts/anomalies/)

**Что делает:**
- Обучает модель Isolation Forest на истории сессий
- Выявляет аномальные паттерны (резкий спад/рост активности)
- Срабатывает при отклонении >3 сигм

**Запуск:**
```bash
# Подготовка данных для обучения
python scripts/anomalies/prepare_training_data.py --days 30

# Обучение модели (раз в неделю)
python scripts/anomalies/train_anomaly_detector.py --input training_data.csv

# Проверка текущих метрик (каждый час)
python scripts/anomalies/detect_anomalies.py
```

**Пример результата:**
```
🔍 ДЕТЕКТОР АНОМАЛИЙ
⏰ 10:00 - обычно 150 сессий
📉 Сейчас: 40 сессий (отклонение 5.5σ)
⚠️ Аномалия! Возможно, проблемы с доступом
```

---

## 📋 ITSM-интеграция

**Файлы:** [`scripts/itsm/`](scripts/itsm/)

### Поддерживаемые системы

| Система | Файл | Статус |
|---------|------|--------|
| Jira Cloud/Server | `jira_integration.py` | ✅ Стабильно |
| YouTrack | `youtrack_integration.py` | ✅ Стабильно |
| ServiceNow | `servicenow_integration.py` | ✅ Стабильно |
| Redmine | `redmine_integration.py` | ✅ Стабильно |
| GitLab Issues | `gitlab_integration.py` | ✅ Стабильно |

### Настройка

```env
# В .env
ITSM_TYPE=jira
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=user@example.com
JIRA_API_TOKEN=token
JIRA_PROJECT_KEY=IT
```

### Использование

```python
from scripts.itsm.factory import create_itsm_client

client = create_itsm_client()
issue_id = client.create_issue(
    summary="Прогноз заполнения диска D:",
    description="Через 14 дней диск достигнет 195 ГБ",
    priority="High",
    due_date="2026-03-10"
)
```

**Документация:** [`docs/itsm.md`](docs/itsm.md)

---

## 🧠 ML для чайников

| Термин | Что это | Пример |
|--------|---------|--------|
| **Регрессия** | Предсказание числа | "Через 7 дней диск будет 175 ГБ" |
| **Классификация** | Отнесение к категории | "85% вероятность дедлока" |
| **Аномалии** | Поиск отклонений | "Сегодня на 70% меньше сессий" |
| **Isolation Forest** | Алгоритм поиска аномалий | Ищет то, что сложно изолировать |
| **Linear Regression** | Линейная регрессия | Проводит прямую через точки данных |
| **Prophet** | Прогноз с сезонностью | Учитывает, что в понедельник нагрузка выше |

**Подробнее:** [`docs/ml_for_dummies.md`](docs/ml_for_dummies.md)

---

## 📊 Результаты пилотного внедрения

> ⚠️ **Важно**: Это результаты тестирования на пилотных контурах, не в промышленной эксплуатации

| Метрика | Результат |
|---------|-----------|
| 🚫 Незапланированные простои | 0 за 3 месяца |
| 📉 Время на разбор инцидентов | -73% |
| ⏰ Прогноз заполнения дисков | за 14 дней |
| 🔍 Раннее обнаружение аномалий | за 3-7 дней |
| 💰 Экономия времени администраторов | ~40 часов/месяц |

---

## 🗺 Roadmap

### ✅ Реализовано
- [x] Прогноз диска (линейная регрессия)
- [x] Сбор метрик Windows через Prometheus
- [x] Дашборды Grafana (диск, блокировки, аномалии)
- [x] Парсер техжурнала в ClickHouse
- [x] Детектор аномалий (Isolation Forest)
- [x] Прогноз дедлоков (анализ трендов)
- [x] Алерты в Telegram
- [x] ITSM-интеграция (Jira, YouTrack, ServiceNow, Redmine, GitLab)

### 🚧 В разработке
- [ ] Модель для прогноза дедлоков на основе Random Forest
- [ ] Интеграция с 1С через HTTP-сервисы
- [ ] Автоматическое перестроение индексов
- [ ] Веб-интерфейс для управления моделями

### 🔮 В планах
- [ ] Поддержка MS SQL Server
- [ ] Интеграция с Zabbix
- [ ] Мобильное приложение для алертов

---

## ❓ FAQ

### ❔ Сколько стоит?
Всё бесплатно и open source. Нужны только серверы для развертывания.

### ❔ Это готовое production-решение?
Нет, это концепт и набор идей. В промышленную эксплуатацию не внедрено, но вы можете доработать под свои задачи.

### ❔ Нужно ли знать математику?
Нет. Все модели уже реализованы, нужно только настроить.

### ❔ Сколько нужно данных для прогноза?
- Диск: минимум 2 недели
- Блокировки: минимум 1 месяц
- Аномалии: минимум 2 месяца

### ❔ Какая точность прогнозов?
- Диск: MAE обычно 2-5 ГБ
- Аномалии: Precision/Recall > 0.8
- Блокировки: тренды видны за 3-7 дней

### ❔ Поддерживается ли MS SQL?
Сейчас в приоритете PostgreSQL. MS SQL в планах.

### ❔ Куда писать, если нашел баг?
Создайте issue на GitHub или напишите в Telegram.

---

## 📬 Контакты

**Айдар Сафин**
- 📧 Email: [safin_ak@magnit.ru](mailto:safin_ak@magnit.ru)

**Полезные ссылки:**
- [Документация](docs/)
- [Issues](https://github.com/aidarsafindev/1CML/issues)
- [Pull Requests](https://github.com/aidarsafindev/1CML/pulls)
- [ITSM-модуль](scripts/itsm/)

---

## 📄 Лицензия

MIT License. Свободно используйте в коммерческих целях.

Copyright (c) 2026 Айдар Сафин, Magnit Tech

---

## ⭐ Поддержка проекта

Если проект помог вам или показался интересным, поставьте звезду на GitHub — это мотивирует развивать его дальше!

[![GitHub stars](https://img.shields.io/github/stars/aidarsafindev/1CML?style=social)](https://github.com/aidarsafindev/1CML)

---

**🚀 Клонируйте, пробуйте, дорабатывайте!**
```
