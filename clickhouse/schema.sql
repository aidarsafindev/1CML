-- Создание базы данных
CREATE DATABASE IF NOT EXISTS techlog;

USE techlog;

-- Таблица для хранения технологического журнала 1С
CREATE TABLE IF NOT EXISTS techlog (
    event_date Date,
    hour UInt8,
    minute UInt8,
    second UInt8,
    millisecond UInt16,
    
    -- Основные метрики
    duration UInt64,
    wait_time UInt64,
    lock_time UInt64,
    transaction UInt64,
    connection UInt32,
    session UInt64,
    
    -- Контекстная информация
    user String,
    computer String,
    app_id String,
    context String,
    dbms String,
    dbpid UInt32,
    func String,
    
    -- Сырая строка для отладки
    raw_line String,
    
    -- Дополнительные метрики
    memory UInt64,
    cpu_time UInt64,
    read_bytes UInt64,
    write_bytes UInt64,
    
    -- Индексы
    INDEX idx_user user TYPE bloom_filter GRANULARITY 1,
    INDEX idx_context context TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 1,
    INDEX idx_duration duration TYPE minmax GRANULARITY 1
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, hour, minute)
TTL event_date + INTERVAL 6 MONTH
SETTINGS index_granularity = 8192;

-- Таблица для агрегированных данных по часам
CREATE TABLE IF NOT EXISTS techlog_hourly (
    event_date Date,
    hour UInt8,
    
    -- Агрегаты
    total_queries UInt64,
    avg_duration Float64,
    max_duration UInt64,
    p95_duration UInt64,
    
    total_wait_time UInt64,
    avg_wait_time Float64,
    
    total_lock_time UInt64,
    avg_lock_time Float64,
    lock_count UInt64,
    
    unique_sessions UInt64,
    unique_users UInt64,
    unique_computers UInt64,
    
    errors UInt64
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, hour);

-- Материализованное представление для агрегации
CREATE MATERIALIZED VIEW IF NOT EXISTS techlog_hourly_mv
TO techlog_hourly
AS
SELECT
    event_date,
    hour,
    count() as total_queries,
    avg(duration) as avg_duration,
    max(duration) as max_duration,
    quantile(0.95)(duration) as p95_duration,
    sum(wait_time) as total_wait_time,
    avg(wait_time) as avg_wait_time,
    sum(lock_time) as total_lock_time,
    avg(lock_time) as avg_lock_time,
    countIf(lock_time > 0) as lock_count,
    uniq(session) as unique_sessions,
    uniq(user) as unique_users,
    uniq(computer) as unique_computers,
    countIf(position(raw_line, 'Exception') > 0) as errors
FROM techlog
GROUP BY event_date, hour;

-- Таблица для хранения метрик производительности
CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_date DateTime,
    metric_name String,
    metric_value Float64,
    tags Map(String, String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(metric_date)
ORDER BY (metric_date, metric_name);
