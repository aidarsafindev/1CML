-- Создание базы данных
CREATE DATABASE IF NOT EXISTS monitoring;

\c monitoring;

-- Таблица для хранения истории заполнения диска
CREATE TABLE IF NOT EXISTS disk_usage (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    disk_letter VARCHAR(2) NOT NULL,
    used_gb FLOAT NOT NULL,
    free_gb FLOAT NOT NULL,
    total_gb FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, disk_letter)
);

CREATE INDEX idx_disk_usage_date ON disk_usage(date);

-- Таблица для хранения прогнозов
CREATE TABLE IF NOT EXISTS disk_forecast (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    disk_used_gb FLOAT,
    forecast_7d_gb FLOAT,
    forecast_14d_gb FLOAT,
    forecast_30d_gb FLOAT,
    growth_rate_gb_per_day FLOAT,
    days_to_limit FLOAT,
    forecast_date TIMESTAMP DEFAULT NOW(),
    UNIQUE(metric_date)
);

CREATE INDEX idx_forecast_date ON disk_forecast(metric_date);

-- Таблица для метрик качества моделей
CREATE TABLE IF NOT EXISTS model_quality (
    id SERIAL PRIMARY KEY,
    train_date TIMESTAMP NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    mae FLOAT,
    r2 FLOAT,
    growth_rate FLOAT,
    accuracy FLOAT,
    precision FLOAT,
    recall FLOAT
);

-- Таблица для обнаруженных аномалий
CREATE TABLE IF NOT EXISTS anomalies (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMP NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    actual_value FLOAT,
    expected_value FLOAT,
    deviation_sigma FLOAT,
    severity VARCHAR(20),
    description TEXT,
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_anomalies_detected ON anomalies(detected_at DESC);

-- Таблица для метрик сессий (подготовка данных для ML)
CREATE TABLE IF NOT EXISTS session_metrics (
    id SERIAL PRIMARY KEY,
    event_time TIMESTAMP NOT NULL,
    session_id VARCHAR(100),
    user_name VARCHAR(100),
    computer VARCHAR(100),
    duration FLOAT,
    lock_time FLOAT,
    wait_time FLOAT,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_session_time ON session_metrics(event_time);
CREATE INDEX idx_session_user ON session_metrics(user_name);

-- Представление для агрегации по часам
CREATE OR REPLACE VIEW hourly_metrics AS
SELECT 
    date_trunc('hour', event_time) as hour,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(*) as total_queries,
    AVG(duration) as avg_duration,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration) as p95_duration,
    SUM(lock_time) as total_lock_time,
    COUNT(CASE WHEN lock_time > 0 THEN 1 END) as lock_count,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as error_count
FROM session_metrics
GROUP BY date_trunc('hour', event_time)
ORDER BY hour DESC;
