-- Создание базы данных
CREATE DATABASE IF NOT EXISTS techlog;

USE techlog;

-- Таблица для хранения всех событий техжурнала
CREATE TABLE IF NOT EXISTS session_events (
    -- Временные метки
    event_date Date,
    event_hour UInt8,
    event_minute UInt8,
    event_datetime DateTime,
    
    -- Данные сессии
    session_id UInt64,
    user_name String,
    computer_name String,
    process_name String,
    app_name String,
    
    -- Метрики производительности
    duration UInt64,          -- в микросекундах
    lock_wait_time UInt64,    -- время ожидания блокировки
    lock_time UInt64,         -- время удержания блокировки
    
    -- Флаги событий
    is_deadlock UInt8,        -- 1 если был дедлок
    is_exception UInt8,       -- 1 если было исключение
    is_timeout UInt8,         -- 1 если был таймаут
    
    -- Сырая строка для отладки
    raw_line String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_hour, user_name)
TTL event_date + INTERVAL 3 MONTH  -- храним 3 месяца
SETTINGS index_granularity = 8192;

-- Таблица для агрегированных данных по часам (для обучения модели)
CREATE TABLE IF NOT EXISTS session_hourly_stats (
    event_date Date,
    event_hour UInt8,
    
    -- Статистика по сессиям
    total_sessions UInt64,
    unique_users UInt64,
    unique_computers UInt64,
    
    -- Распределение по часам (для паттернов)
    avg_sessions_per_minute Float64,
    max_sessions_per_minute UInt64,
    
    -- Метрики производительности
    avg_duration Float64,
    p95_duration Float64,
    max_duration UInt64,
    
    avg_lock_wait_time Float64,
    total_lock_wait_time UInt64,
    
    -- Ошибки и аномалии
    deadlock_count UInt64,
    exception_count UInt64,
    timeout_count UInt64,
    
    -- Флаг выходного/рабочего дня
    is_weekend UInt8,
    is_work_hour UInt8
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_hour);

-- Материализованное представление для автоматической агрегации
CREATE MATERIALIZED VIEW session_hourly_stats_mv
TO session_hourly_stats
AS SELECT
    event_date,
    event_hour,
    count() as total_sessions,
    uniq(user_name) as unique_users,
    uniq(computer_name) as unique_computers,
    avg(duration) as avg_duration,
    quantile(0.95)(duration) as p95_duration,
    max(duration) as max_duration,
    avg(lock_wait_time) as avg_lock_wait_time,
    sum(lock_wait_time) as total_lock_wait_time,
    sum(is_deadlock) as deadlock_count,
    sum(is_exception) as exception_count,
    sum(is_timeout) as timeout_count
FROM session_events
GROUP BY event_date, event_hour;
