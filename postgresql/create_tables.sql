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
CREATE INDEX idx_disk_usage_letter ON disk_usage(disk_letter);

-- Таблица для хранения прогнозов
CREATE TABLE IF NOT EXISTS disk_forecast (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,           -- дата, на которую сделан прогноз
    disk_letter VARCHAR(2) NOT NULL,
    
    -- Фактические данные на дату прогноза
    actual_used_gb FLOAT,
    
    -- Прогнозы
    forecast_7d_gb FLOAT,                 -- прогноз через 7 дней
    forecast_14d_gb FLOAT,                -- прогноз через 14 дней
    forecast_30d_gb FLOAT,                -- прогноз через 30 дней
    
    -- Метрики модели
    growth_rate_gb_per_day FLOAT,         -- скорость роста (коэффициент регрессии)
    days_to_limit FLOAT,                   -- дней до заполнения
    confidence_interval_lower FLOAT,       -- нижняя граница доверительного интервала
    confidence_interval_upper FLOAT,       -- верхняя граница доверительного интервала
    
    -- Качество модели
    mae FLOAT,                             -- средняя абсолютная ошибка
    r2 FLOAT,                              -- коэффициент детерминации
    
    forecast_date TIMESTAMP DEFAULT NOW(),
    UNIQUE(metric_date, disk_letter)
);

CREATE INDEX idx_forecast_date ON disk_forecast(metric_date);
CREATE INDEX idx_forecast_letter ON disk_forecast(disk_letter);

-- Таблица для метрик качества моделей
CREATE TABLE IF NOT EXISTS model_quality (
    id SERIAL PRIMARY KEY,
    train_date TIMESTAMP NOT NULL,
    disk_letter VARCHAR(2) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    mae FLOAT,
    r2 FLOAT,
    growth_rate FLOAT,
    samples_count INTEGER,
    training_days INTEGER
);

-- Таблица для алертов
CREATE TABLE IF NOT EXISTS disk_alerts (
    id SERIAL PRIMARY KEY,
    alert_date TIMESTAMP NOT NULL,
    disk_letter VARCHAR(2) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,      -- warning, critical
    forecast_days INTEGER,                  -- через сколько дней проблема
    current_used_gb FLOAT,
    forecast_used_gb FLOAT,
    threshold_gb FLOAT,
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    jira_ticket VARCHAR(50)
);

CREATE INDEX idx_alerts_date ON disk_alerts(alert_date DESC);

-- Представление для Grafana (текущее состояние + прогноз)
CREATE OR REPLACE VIEW disk_status AS
SELECT 
    du.date,
    du.disk_letter,
    du.used_gb as actual_used,
    df.forecast_7d_gb,
    df.forecast_14d_gb,
    df.forecast_30d_gb,
    df.growth_rate_gb_per_day,
    df.days_to_limit,
    CASE 
        WHEN df.days_to_limit <= 7 THEN 'critical'
        WHEN df.days_to_limit <= 14 THEN 'warning'
        WHEN df.days_to_limit <= 30 THEN 'info'
        ELSE 'normal'
    END as status
FROM disk_usage du
LEFT JOIN disk_forecast df ON du.date = df.metric_date AND du.disk_letter = df.disk_letter
ORDER BY du.date DESC;
