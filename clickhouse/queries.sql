-- Полезные запросы для анализа техжурнала

-- 1. Самые медленные операции за последний час
SELECT 
    context,
    count() as cnt,
    avg(duration) as avg_duration,
    max(duration) as max_duration,
    sum(duration) as total_duration
FROM techlog
WHERE event_date = today() 
  AND hour >= toHour(now()) - 1
GROUP BY context
ORDER BY avg_duration DESC
LIMIT 20;

-- 2. Динамика блокировок по дням
SELECT 
    event_date,
    count() as total_ops,
    sum(lock_time) as total_lock_time,
    avg(lock_time) as avg_lock_time,
    countIf(lock_time > 1000000) as long_locks  -- блокировки > 1 сек
FROM techlog
WHERE event_date >= today() - 30
GROUP BY event_date
ORDER BY event_date;

-- 3. Топ пользователей по нагрузке
SELECT 
    user,
    count() as queries,
    avg(duration) as avg_duration,
    sum(duration) as total_duration,
    uniq(session) as sessions
FROM techlog
WHERE event_date >= today() - 7
  AND user != ''
GROUP BY user
ORDER BY total_duration DESC
LIMIT 20;

-- 4. Анализ дедлоков (поиск паттернов)
SELECT 
    toStartOfHour(event_date) as hour,
    countIf(position(lower(raw_line), 'deadlock') > 0) as deadlocks,
    avg(lock_time) as avg_lock_time,
    max(lock_time) as max_lock_time
FROM techlog
WHERE event_date >= today() - 30
  AND lock_time > 0
GROUP BY hour
HAVING deadlocks > 0
ORDER BY hour DESC;

-- 5. Корреляция между количеством сессий и временем ожидания
SELECT 
    toHour(event_date) as hour_of_day,
    uniq(session) as sessions,
    avg(wait_time) as avg_wait_time,
    avg(duration) as avg_duration
FROM techlog
WHERE event_date >= today() - 7
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- 6. Прогноз роста (подготовка данных для Python)
SELECT 
    event_date,
    count() as operations,
    sum(duration) as total_duration,
    max(duration) as peak_duration,
    avg(lock_time) as avg_lock_time
FROM techlog
WHERE event_date >= today() - 60
GROUP BY event_date
ORDER BY event_date;

-- 7. Самые частые ошибки
SELECT 
    extract(raw_line, 'Exception in .*?: (.*?)\\n') as error_text,
    count() as cnt,
    uniq(session) as affected_sessions
FROM techlog
WHERE position(raw_line, 'Exception') > 0
  AND event_date >= today() - 7
GROUP BY error_text
ORDER BY cnt DESC
LIMIT 20;

-- 8. Аномалии в активности (отклонение от среднего)
WITH daily_stats AS (
    SELECT 
        event_date,
        count() as queries,
        uniq(session) as sessions
    FROM techlog
    WHERE event_date >= today() - 30
    GROUP BY event_date
)
SELECT 
    event_date,
    queries,
    sessions,
    avg(queries) OVER (ORDER BY event_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as avg_7d,
    stddev(queries) OVER (ORDER BY event_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as std_7d,
    (queries - avg_7d) / std_7d as deviation
FROM daily_stats
ORDER BY event_date;
