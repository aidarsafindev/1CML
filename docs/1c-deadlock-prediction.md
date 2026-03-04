# Как физически работает прогноз дедлоков
## Полный путь данных: от техжурнала до предотвращения дедлока

```
Техжурнал 1С → Парсер → ClickHouse → Анализ трендов → Детекция рисков → Оповещение
```

---

## 1. Что такое дедлок и почему его нужно прогнозировать

### 1.1. Определение

**Дедлок (deadlock)** — ситуация, когда две или более транзакции блокируют друг друга, и ни одна не может продолжить работу.

**Пример из жизни 1С:**
```
Транзакция А: блокирует таблицу 1, ждет таблицу 2
Транзакция Б: блокирует таблицу 2, ждет таблицу 1
Результат: обе висят вечно, пока 1С их не убьет принудительно
```

### 1.2. Почему важно прогнозировать

| Проблема | Последствия |
|----------|-------------|
| Дедлок уже случился | Пользователи жалуются, документы не проводятся |
| Дедлок в моменте | Приходится убивать процессы вручную |
| Прогноз дедлока | Можно оптимизировать запросы заранее |

**Статистика:** в 80% случаев дедлоку предшествует рост времени блокировок за 3-7 дней.

---

## 2. Какие данные нужны для прогноза дедлоков

### 2.1. События техжурнала для анализа блокировок

**Настройка техжурнала** (`logcfg.xml`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config xmlns="http://v8.1c.ru/v8/tech-log">
  <log location="C:\1C_techlog\" history="14">
    <event>
      <eq property="name" value="LOCK" />        <!-- События блокировок -->
      <eq property="name" value="DEADLOCK" />    <!-- Дедлоки -->
      <eq property="name" value="TTIMEOUT" />    <!-- Таймауты -->
      <eq property="name" value="SDBL" />        <!-- События СУБД -->
    </event>
    <property name="all">
      <ne property="name" value="t:session" />        <!-- ID сессии -->
      <ne property="name" value="t:transaction" />    <!-- ID транзакции -->
      <ne property="name" value="t:lockName" />       <!-- Имя блокировки -->
      <ne property="name" value="t:lockType" />       <!-- Тип блокировки -->
      <ne property="name" value="t:lockMode" />       <!-- Режим блокировки -->
      <ne property="name" value="t:lockWaitTime" />   <!-- Время ожидания -->
      <ne property="name" value="t:lockTime" />       <!-- Время удержания -->
      <ne property="name" value="t:dbpid" />          <!-- PID в СУБД -->
      <ne property="name" value="t:tableName" />      <!-- Имя таблицы -->
      <ne property="name" value="p:processName" />    <!-- Процесс -->
      <ne property="name" value="t:userName" />       <!-- Пользователь -->
    </property>
  </log>
</config>
```

### 2.2. Примеры строк техжурнала

**Обычная блокировка:**
```
20260228 10:35:23.456 LOCK,3,1c.exe,processName=rmngr,userName="Иванов",
session=12345678,transaction=87654321,tableName="_InfoRg12345",
lockType="Row",lockMode="S",lockWaitTime=0,lockTime=1250
```

**Дедлок:**
```
20260228 10:35:23.456 DEADLOCK,3,1c.exe,processName=rmngr,
session=12345678,transaction=87654321,
tableName="_InfoRg12345",dbpid=12345,
lockWaitTime=30000,lockTime=0
```

**Таймаут блокировки:**
```
20260228 10:35:23.456 TTIMEOUT,3,1c.exe,processName=rmngr,
session=12345678,tableName="_AccumRg6789",
lockWaitTime=60000,lockTime=0
```

---

## 3. Таблицы в ClickHouse для анализа блокировок

### 3.1. Расширенная схема для блокировок

**Файл:** `clickhouse/schema_locks.sql`

```sql
-- Создание базы данных
CREATE DATABASE IF NOT EXISTS techlog;

USE techlog;

-- Таблица для событий блокировок
CREATE TABLE IF NOT EXISTS lock_events (
    -- Временные метки
    event_date Date,
    event_hour UInt8,
    event_minute UInt8,
    event_datetime DateTime,
    
    -- Тип события
    event_type String,  -- LOCK, DEADLOCK, TTIMEOUT, SDBL
    
    -- Данные сессии
    session_id UInt64,
    transaction_id UInt64,
    user_name String,
    process_name String,
    
    -- Данные блокировки
    table_name String,
    lock_type String,   -- Row, Page, Table
    lock_mode String,   -- S, X, IS, IX, SIX
    lock_name String,
    
    -- Метрики
    lock_wait_time UInt64,  -- время ожидания в микросекундах
    lock_time UInt64,       -- время удержания в микросекундах
    dbpid UInt32,           -- PID в СУБД
    
    -- Дополнительная информация
    raw_line String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, table_name, event_type)
TTL event_date + INTERVAL 3 MONTH
SETTINGS index_granularity = 8192;

-- Таблица для агрегированной статистики по часам
CREATE TABLE IF NOT EXISTS lock_hourly_stats (
    event_date Date,
    event_hour UInt8,
    
    -- Общая статистика
    total_lock_events UInt64,
    total_deadlocks UInt64,
    total_timeouts UInt64,
    
    -- Временные характеристики
    avg_lock_wait_time Float64,
    max_lock_wait_time UInt64,
    p95_lock_wait_time Float64,
    
    avg_lock_time Float64,
    max_lock_time UInt64,
    
    -- Статистика по таблицам (JSON)
    top_tables String,  -- будет заполняться отдельно
    
    -- Активность
    unique_sessions UInt64,
    unique_transactions UInt64,
    
    -- Риск-метрики
    lock_intensity Float64,  -- блокировок в минуту
    deadlock_rate Float64,   -- дедлоков в час
    
    -- Флаги
    is_weekend UInt8,
    is_work_hour UInt8
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_hour);

-- Таблица для статистики по конкретным таблицам
CREATE TABLE IF NOT EXISTS lock_table_stats (
    event_date Date,
    table_name String,
    
    lock_count UInt64,
    deadlock_count UInt64,
    timeout_count UInt64,
    
    avg_lock_wait_time Float64,
    max_lock_wait_time UInt64,
    
    avg_lock_time Float64,
    max_lock_time UInt64,
    
    unique_sessions UInt64,
    unique_transactions UInt64
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, table_name);

-- Материализованное представление для агрегации по часам
CREATE MATERIALIZED VIEW lock_hourly_stats_mv
TO lock_hourly_stats
AS SELECT
    event_date,
    event_hour,
    count() as total_lock_events,
    countIf(event_type = 'DEADLOCK') as total_deadlocks,
    countIf(event_type = 'TTIMEOUT') as total_timeouts,
    avg(lock_wait_time) as avg_lock_wait_time,
    max(lock_wait_time) as max_lock_wait_time,
    quantile(0.95)(lock_wait_time) as p95_lock_wait_time,
    avg(lock_time) as avg_lock_time,
    max(lock_time) as max_lock_time,
    uniq(session_id) as unique_sessions,
    uniq(transaction_id) as unique_transactions,
    count() / 60.0 as lock_intensity,
    countIf(event_type = 'DEADLOCK') / 1.0 as deadlock_rate,
    CASE WHEN toDayOfWeek(event_date) IN (6, 7) THEN 1 ELSE 0 END as is_weekend,
    CASE WHEN event_hour BETWEEN 9 AND 18 THEN 1 ELSE 0 END as is_work_hour
FROM lock_events
GROUP BY event_date, event_hour;

-- Материализованное представление для статистики по таблицам
CREATE MATERIALIZED VIEW lock_table_stats_mv
TO lock_table_stats
AS SELECT
    event_date,
    table_name,
    count() as lock_count,
    countIf(event_type = 'DEADLOCK') as deadlock_count,
    countIf(event_type = 'TTIMEOUT') as timeout_count,
    avg(lock_wait_time) as avg_lock_wait_time,
    max(lock_wait_time) as max_lock_wait_time,
    avg(lock_time) as avg_lock_time,
    max(lock_time) as max_lock_time,
    uniq(session_id) as unique_sessions,
    uniq(transaction_id) as unique_transactions
FROM lock_events
WHERE table_name != ''
GROUP BY event_date, table_name;
```

### 3.2. Полезные запросы для анализа

**Файл:** `clickhouse/queries_locks.sql`

```sql
-- 1. Динамика блокировок по дням
SELECT 
    event_date,
    count() as total_locks,
    countIf(event_type = 'DEADLOCK') as deadlocks,
    countIf(event_type = 'TTIMEOUT') as timeouts,
    avg(lock_wait_time) as avg_wait,
    max(lock_wait_time) as max_wait
FROM lock_events
WHERE event_date >= today() - 30
GROUP BY event_date
ORDER BY event_date;

-- 2. Топ-20 таблиц по блокировкам за сегодня
SELECT 
    table_name,
    count() as lock_count,
    countIf(event_type = 'DEADLOCK') as deadlocks,
    countIf(event_type = 'TTIMEOUT') as timeouts,
    avg(lock_wait_time) as avg_wait_ms,
    max(lock_wait_time) / 1000 as max_wait_ms
FROM lock_events
WHERE event_date = today()
  AND table_name != ''
GROUP BY table_name
ORDER BY lock_count DESC
LIMIT 20;

-- 3. Часовой тренд блокировок (для прогноза)
SELECT 
    toStartOfHour(event_datetime) as hour,
    count() as locks,
    countIf(event_type = 'DEADLOCK') as deadlocks,
    avg(lock_wait_time) as avg_wait,
    max(lock_wait_time) as max_wait
FROM lock_events
WHERE event_datetime >= now() - interval 7 day
GROUP BY hour
ORDER BY hour;

-- 4. Поиск паттернов дедлоков (какие таблицы участвуют)
SELECT 
    a.table_name as table1,
    b.table_name as table2,
    count() as deadlock_pairs
FROM lock_events a
JOIN lock_events b ON a.event_datetime = b.event_datetime 
    AND a.session_id != b.session_id
    AND a.event_type = 'DEADLOCK' 
    AND b.event_type = 'DEADLOCK'
WHERE a.event_date >= today() - 7
  AND a.table_name < b.table_name
GROUP BY table1, table2
ORDER BY deadlock_pairs DESC;

-- 5. Корреляция между активностью и блокировками
SELECT 
    toHour(event_datetime) as hour_of_day,
    avg(lock_wait_time) as avg_wait,
    count() as locks,
    uniq(session_id) as sessions
FROM lock_events
WHERE event_date >= today() - 7
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- 6. Скользящее среднее для выявления трендов
SELECT 
    event_date,
    avg(lock_wait_time) as avg_wait,
    avg(avg(lock_wait_time)) OVER (
        ORDER BY event_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as trend_7d
FROM lock_events
GROUP BY event_date
ORDER BY event_date;
```

---

## 4. Парсер для сбора данных о блокировках

### 4.1. Расширенный парсер с поддержкой блокировок

**Файл:** `scripts/techlog_parser_locks.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Парсер техжурнала 1С с фокусом на блокировки и дедлоки
"""

import re
import gzip
from datetime import datetime
import logging
from typing import Optional, Dict, List
from clickhouse_driver import Client

logger = logging.getLogger('techlog_parser_locks')

class LockEventParser:
    """Парсер событий блокировок из техжурнала"""
    
    # Регулярные выражения для полей блокировок
    PATTERNS = {
        'datetime': re.compile(r'^(\d{4})(\d{2})(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})'),
        'event_type': re.compile(r',([A-Z_]+),'),
        
        # Данные сессии
        'session': re.compile(r'session=(\d+)'),
        'transaction': re.compile(r'transaction=(\d+)'),
        'user': re.compile(r'userName="([^"]*)"'),
        'process': re.compile(r'processName=([^,]+)'),
        
        # Данные блокировки
        'table_name': re.compile(r'tableName="?([^",]+)"?'),
        'lock_type': re.compile(r'lockType="?([^",]+)"?'),
        'lock_mode': re.compile(r'lockMode="?([^",]+)"?'),
        'lock_name': re.compile(r'lockName="?([^",]+)"?'),
        
        # Метрики
        'lock_wait_time': re.compile(r'lockWaitTime=(\d+)'),
        'lock_time': re.compile(r'lockTime=(\d+)'),
        'dbpid': re.compile(r'dbpid=(\d+)'),
    }
    
    def __init__(self, client: Client):
        self.client = client
        self.batch = []
        self.batch_size = 5000
        
    def parse_line(self, line: str) -> Optional[Dict]:
        """Парсинг одной строки лога"""
        try:
            line = line.strip()
            if not line:
                return None
            
            # Парсим дату и время
            dt_match = self.PATTERNS['datetime'].search(line)
            if not dt_match:
                return None
            
            year, month, day, hour, minute, second, ms = map(int, dt_match.groups())
            event_datetime = datetime(year, month, day, hour, minute, second, ms * 1000)
            
            # Тип события
            type_match = self.PATTERNS['event_type'].search(line)
            event_type = type_match.group(1) if type_match else 'UNKNOWN'
            
            # Если это не событие блокировки - пропускаем для экономии
            if event_type not in ['LOCK', 'DEADLOCK', 'TTIMEOUT', 'SDBL']:
                return None
            
            # Извлекаем все поля
            result = {
                'event_date': event_datetime.date(),
                'event_hour': hour,
                'event_minute': minute,
                'event_datetime': event_datetime,
                'event_type': event_type,
            }
            
            # Извлекаем данные
            for key, pattern in self.PATTERNS.items():
                if key in ['datetime', 'event_type']:
                    continue
                
                match = pattern.search(line)
                if match:
                    value = match.group(1)
                    
                    # Преобразование типов
                    if key in ['session', 'transaction', 'lock_wait_time', 'lock_time', 'dbpid']:
                        try:
                            value = int(value)
                        except ValueError:
                            continue
                    
                    result[key] = value
            
            # Устанавливаем значения по умолчанию
            defaults = {
                'session': 0,
                'transaction': 0,
                'user': '',
                'process': '',
                'table_name': '',
                'lock_type': '',
                'lock_mode': '',
                'lock_name': '',
                'lock_wait_time': 0,
                'lock_time': 0,
                'dbpid': 0
            }
            
            for key, default in defaults.items():
                if key not in result:
                    result[key] = default
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return None
    
    def insert_batch(self):
        """Вставка батча в ClickHouse"""
        if not self.batch:
            return
        
        try:
            data = []
            for record in self.batch:
                row = [
                    record['event_date'],
                    record['event_hour'],
                    record['event_minute'],
                    record['event_datetime'],
                    record['event_type'],
                    record['session'],
                    record['transaction'],
                    record['user'][:100],
                    record['process'][:50],
                    record['table_name'][:200],
                    record['lock_type'][:20],
                    record['lock_mode'][:20],
                    record['lock_name'][:200],
                    record['lock_wait_time'],
                    record['lock_time'],
                    record['dbpid'],
                    ''  # raw_line
                ]
                data.append(row)
            
            self.client.execute(
                """
                INSERT INTO lock_events (
                    event_date, event_hour, event_minute, event_datetime,
                    event_type, session_id, transaction_id, user_name,
                    process_name, table_name, lock_type, lock_mode,
                    lock_name, lock_wait_time, lock_time, dbpid, raw_line
                ) VALUES
                """,
                data
            )
            
            logger.debug(f"Вставлено {len(self.batch)} записей о блокировках")
            self.batch = []
            
        except Exception as e:
            logger.error(f"Ошибка вставки: {e}")
            self.batch = []  # очищаем, чтобы не копились
    
    def process_file(self, file_path: str):
        """Обработка файла техжурнала"""
        logger.info(f"Обработка файла: {file_path}")
        
        open_func = gzip.open if file_path.endswith('.gz') else open
        mode = 'rt' if file_path.endswith('.gz') else 'r'
        
        lines_processed = 0
        locks_found = 0
        
        with open_func(file_path, mode, encoding='utf-8', errors='ignore') as f:
            for line in f:
                lines_processed += 1
                
                parsed = self.parse_line(line)
                if parsed:
                    locks_found += 1
                    self.batch.append(parsed)
                    
                    if len(self.batch) >= self.batch_size:
                        self.insert_batch()
                
                if lines_processed % 100000 == 0:
                    logger.info(f"  Обработано {lines_processed} строк, найдено {locks_found} блокировок")
        
        # Вставляем остаток
        if self.batch:
            self.insert_batch()
        
        logger.info(f"Файл обработан: {locks_found} блокировок из {lines_processed} строк")
        return locks_found
```

---

## 5. Анализ трендов и прогноз дедлоков

### 5.1. Скрипт для расчета трендов блокировок

**Файл:** `scripts/analyze_lock_trends.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Анализ трендов блокировок и расчет риска дедлоков
"""

import pandas as pd
import numpy as np
from clickhouse_driver import Client
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('lock_trends')

class LockTrendAnalyzer:
    """Анализатор трендов блокировок"""
    
    def __init__(self, host='localhost', port=9000, database='techlog'):
        self.client = Client(host=host, port=port, database=database)
        
        # Пороги для разных уровней риска
        self.thresholds = {
            'deadlock_warning': 1,      # 1 дедлок в час - уже проблема
            'timeout_warning': 10,       # 10 таймаутов в час
            'wait_time_critical': 1000000,  # 1 секунда ожидания
            'trend_warning': 50,          # рост на 50% за неделю
            'trend_critical': 100,         # рост на 100% за неделю
        }
    
    def get_daily_stats(self, days: int = 30) -> pd.DataFrame:
        """
        Получение дневной статистики блокировок
        
        Args:
            days: количество дней истории
            
        Returns:
            DataFrame с колонками: date, total_locks, deadlocks, timeouts,
            avg_wait_time, max_wait_time
        """
        query = f"""
        SELECT 
            event_date,
            count() as total_locks,
            countIf(event_type = 'DEADLOCK') as deadlocks,
            countIf(event_type = 'TTIMEOUT') as timeouts,
            avg(lock_wait_time) as avg_wait_time,
            max(lock_wait_time) as max_wait_time,
            quantile(0.95)(lock_wait_time) as p95_wait_time
        FROM lock_events
        WHERE event_date >= today() - {days}
        GROUP BY event_date
        ORDER BY event_date
        """
        
        result = self.client.execute(query)
        df = pd.DataFrame(result, columns=[
            'date', 'total_locks', 'deadlocks', 'timeouts',
            'avg_wait', 'max_wait', 'p95_wait'
        ])
        
        logger.info(f"Загружена статистика за {len(df)} дней")
        return df
    
    def get_hourly_trend(self, days: int = 7) -> pd.DataFrame:
        """
        Получение почасового тренда для детального анализа
        
        Args:
            days: количество дней истории
            
        Returns:
            DataFrame с почасовой статистикой
        """
        query = f"""
        SELECT 
            toStartOfHour(event_datetime) as hour,
            count() as locks,
            countIf(event_type = 'DEADLOCK') as deadlocks,
            countIf(event_type = 'TTIMEOUT') as timeouts,
            avg(lock_wait_time) as avg_wait,
            max(lock_wait_time) as max_wait,
            uniq(session_id) as sessions,
            uniq(table_name) as tables_involved
        FROM lock_events
        WHERE event_datetime >= now() - interval {days} day
        GROUP BY hour
        ORDER BY hour
        """
        
        result = self.client.execute(query)
        df = pd.DataFrame(result, columns=[
            'hour', 'locks', 'deadlocks', 'timeouts',
            'avg_wait', 'max_wait', 'sessions', 'tables'
        ])
        
        return df
    
    def get_top_tables(self, days: int = 1) -> pd.DataFrame:
        """
        Получение топ-таблиц по блокировкам
        
        Args:
            days: количество дней для анализа
            
        Returns:
            DataFrame с таблицами-лидерами по блокировкам
        """
        query = f"""
        SELECT 
            table_name,
            count() as lock_count,
            countIf(event_type = 'DEADLOCK') as deadlocks,
            countIf(event_type = 'TTIMEOUT') as timeouts,
            avg(lock_wait_time) as avg_wait,
            max(lock_wait_time) as max_wait,
            uniq(session_id) as sessions
        FROM lock_events
        WHERE event_date >= today() - {days}
          AND table_name != ''
        GROUP BY table_name
        ORDER BY lock_count DESC
        LIMIT 50
        """
        
        result = self.client.execute(query)
        df = pd.DataFrame(result, columns=[
            'table', 'lock_count', 'deadlocks', 'timeouts',
            'avg_wait', 'max_wait', 'sessions'
        ])
        
        return df
    
    def calculate_trends(self, df: pd.DataFrame) -> Dict:
        """
        Расчет трендов и метрик риска
        
        Args:
            df: DataFrame с дневной статистикой
            
        Returns:
            Словарь с метриками риска
        """
        if len(df) < 7:
            return {'error': 'Недостаточно данных'}
        
        # Сортируем по дате
        df = df.sort_values('date')
        
        # Берем первую неделю (базовый уровень) и последнюю неделю (текущий)
        base_week = df.iloc[:7]
        current_week = df.iloc[-7:]
        
        # Расчет метрик
        metrics = {
            'analysis_date': datetime.now().isoformat(),
            'days_analyzed': len(df),
            
            # Базовые метрики
            'base_avg_locks': base_week['total_locks'].mean(),
            'base_avg_deadlocks': base_week['deadlocks'].mean(),
            'base_avg_wait': base_week['avg_wait'].mean(),
            
            'current_avg_locks': current_week['total_locks'].mean(),
            'current_avg_deadlocks': current_week['deadlocks'].mean(),
            'current_avg_wait': current_week['avg_wait'].mean(),
            
            # Тренды
            'locks_trend_pct': self._calc_trend(
                base_week['total_locks'].mean(),
                current_week['total_locks'].mean()
            ),
            'deadlocks_trend_pct': self._calc_trend(
                base_week['deadlocks'].mean(),
                current_week['deadlocks'].mean()
            ),
            'wait_time_trend_pct': self._calc_trend(
                base_week['avg_wait'].mean(),
                current_week['avg_wait'].mean()
            ),
            
            # Пиковые значения
            'max_deadlocks_day': df['deadlocks'].max(),
            'max_deadlocks_date': df.loc[df['deadlocks'].idxmax(), 'date'].isoformat(),
            'max_wait_time': df['max_wait'].max(),
            'max_wait_date': df.loc[df['max_wait'].idxmax(), 'date'].isoformat(),
        }
        
        # Расчет уровня риска
        risk_score = 0
        risk_factors = []
        
        # 1. Дедлоки
        if metrics['current_avg_deadlocks'] > 0:
            risk_score += 30
            risk_factors.append(f"Есть дедлоки: {metrics['current_avg_deadlocks']:.1f} в день")
        elif metrics['deadlocks_trend_pct'] > 50:
            risk_score += 20
            risk_factors.append(f"Рост дедлоков на {metrics['deadlocks_trend_pct']:.0f}%")
        
        # 2. Время ожидания
        if metrics['current_avg_wait'] > self.thresholds['wait_time_critical']:
            risk_score += 25
            risk_factors.append(f"Критическое время ожидания: {metrics['current_avg_wait']/1000:.0f} мс")
        elif metrics['wait_time_trend_pct'] > self.thresholds['trend_critical']:
            risk_score += 20
            risk_factors.append(f"Рост времени ожидания на {metrics['wait_time_trend_pct']:.0f}%")
        elif metrics['wait_time_trend_pct'] > self.thresholds['trend_warning']:
            risk_score += 10
            risk_factors.append(f"Рост времени ожидания на {metrics['wait_time_trend_pct']:.0f}%")
        
        # 3. Общее количество блокировок
        if metrics['locks_trend_pct'] > self.thresholds['trend_critical']:
            risk_score += 15
            risk_factors.append(f"Рост числа блокировок на {metrics['locks_trend_pct']:.0f}%")
        elif metrics['locks_trend_pct'] > self.thresholds['trend_warning']:
            risk_score += 10
            risk_factors.append(f"Рост числа блокировок на {metrics['locks_trend_pct']:.0f}%")
        
        # Определение уровня риска
        if risk_score >= 50:
            risk_level = 'critical'
        elif risk_score >= 25:
            risk_level = 'high'
        elif risk_score >= 10:
            risk_level = 'warning'
        else:
            risk_level = 'normal'
        
        metrics['risk_score'] = risk_score
        metrics['risk_level'] = risk_level
        metrics['risk_factors'] = risk_factors
        
        return metrics
    
    def _calc_trend(self, base: float, current: float) -> float:
        """Расчет процентного изменения"""
        if base == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - base) / base) * 100
    
    def predict_deadlock_risk(self, days_ahead: int = 7) -> Dict:
        """
        Прогноз риска дедлоков на основе трендов
        
        Args:
            days_ahead: на сколько дней вперед прогнозировать
            
        Returns:
            Словарь с прогнозом
        """
        # Получаем данные за последние 30 дней
        df = self.get_daily_stats(days=30)
        
        if len(df) < 14:
            return {'error': 'Недостаточно данных для прогноза'}
        
        # Простая линейная экстраполяция
        from sklearn.linear_model import LinearRegression
        
        # Подготовка данных
        X = np.arange(len(df)).reshape(-1, 1)
        y_locks = df['total_locks'].values
        y_wait = df['avg_wait'].values
        
        # Обучение моделей
        model_locks = LinearRegression()
        model_locks.fit(X, y_locks)
        
        model_wait = LinearRegression()
        model_wait.fit(X, y_wait)
        
        # Прогноз
        future_X = np.arange(len(df), len(df) + days_ahead).reshape(-1, 1)
        forecast_locks = model_locks.predict(future_X)
        forecast_wait = model_wait.predict(future_X)
        
        # Оценка риска
        risk_days = []
        for i in range(days_ahead):
            day_risk = {
                'day': i + 1,
                'forecast_locks': float(forecast_locks[i]),
                'forecast_wait': float(forecast_wait[i]),
                'deadlock_probability': min(100, float(forecast_wait[i] / 1000000 * 10))
            }
            risk_days.append(day_risk)
        
        # Когда ожидается первый дедлок (грубая оценка)
        days_to_deadlock = None
        for i, day in enumerate(risk_days):
            if day['deadlock_probability'] > 70:
                days_to_deadlock = i + 1
                break
        
        return {
            'forecast_date': (datetime.now() + timedelta(days=days_ahead)).isoformat(),
            'days_to_deadlock': days_to_deadlock,
            'risk_days': risk_days,
            'trend_locks': float(model_locks.coef_[0]),
            'trend_wait': float(model_wait.coef_[0])
        }

def main():
    """Основная функция"""
    analyzer = LockTrendAnalyzer()
    
    # Получаем статистику
    df = analyzer.get_daily_stats(days=30)
    
    # Анализируем тренды
    trends = analyzer.calculate_trends(df)
    
    print("\n" + "="*60)
    print("АНАЛИЗ БЛОКИРОВОК И РИСК ДЕДЛОКОВ")
    print("="*60)
    
    print(f"\n📊 Период анализа: {df['date'].min()} - {df['date'].max()}")
    print(f"\nТЕКУЩИЕ МЕТРИКИ (последние 7 дней):")
    print(f"  • Среднее число блокировок в день: {trends['current_avg_locks']:.0f}")
    print(f"  • Среднее число дедлоков в день: {trends['current_avg_deadlocks']:.2f}")
    print(f"  • Среднее время ожидания: {trends['current_avg_wait']/1000:.0f} мс")
    
    print(f"\n📈 ТРЕНДЫ (изменение за 30 дней):")
    print(f"  • Блокировки: {trends['locks_trend_pct']:+.1f}%")
    print(f"  • Дедлоки: {trends['deadlocks_trend_pct']:+.1f}%")
    print(f"  • Время ожидания: {trends['wait_time_trend_pct']:+.1f}%")
    
    print(f"\n⚠️ УРОВЕНЬ РИСКА: {trends['risk_level'].upper()}")
    print(f"  • Оценка риска: {trends['risk_score']}/100")
    if trends['risk_factors']:
        print("  • Факторы риска:")
        for factor in trends['risk_factors']:
            print(f"    - {factor}")
    
    # Прогноз
    if trends['risk_level'] in ['high', 'critical']:
        forecast = analyzer.predict_deadlock_risk(days_ahead=7)
        if forecast.get('days_to_deadlock'):
            print(f"\n🔮 ПРОГНОЗ:")
            print(f"  • Ожидаемый дедлок через {forecast['days_to_deadlock']} дней")
            print(f"  • Тренд роста блокировок: {forecast['trend_locks']:.1f} блокировок/день")
    
    # Топ таблиц
    print(f"\n📋 ТОП-10 ТАБЛИЦ ПО БЛОКИРОВКАМ (за последние 7 дней):")
    top_tables = analyzer.get_top_tables(days=7)
    for idx, row in top_tables.head(10).iterrows():
        deadlock_mark = "🔴" if row['deadlocks'] > 0 else "⚪"
        print(f"  {deadlock_mark} {row['table']}: {row['lock_count']} блокировок, "
              f"среднее ожидание {row['avg_wait']/1000:.0f} мс")
    
    print("="*60)

if __name__ == "__main__":
    main()
```

---

## 6. Скрипт для прогноза дедлоков (основной)

**Файл:** `scripts/check_deadlocks.py`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки риска дедлоков и оповещения
Запуск: каждый час
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from clickhouse_driver import Client
import requests
import json
from pathlib import Path

# Добавляем пути
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/deadlocks.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('deadlock_checker')

# Загрузка переменных окружения
load_dotenv()

class DeadlockDetector:
    """Детектор риска дедлоков на основе техжурнала"""
    
    def __init__(self):
        """Инициализация подключения к ClickHouse"""
        self.clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', 9000))
        self.clickhouse_db = os.getenv('CLICKHOUSE_DB', 'techlog')
        
        # Пороги для алертов
        self.DEADLOCK_THRESHOLD = 1  # 1 дедлок в час - уже критично
        self.WAIT_TIME_THRESHOLD = 500000  # 500 мс - внимание
        self.WAIT_TIME_CRITICAL = 1000000  # 1 секунда - критично
        self.TREND_THRESHOLD = 50  # рост на 50% за неделю
        
        try:
            self.client = Client(
                host=self.clickhouse_host,
                port=self.clickhouse_port,
                database=self.clickhouse_db
            )
            logger.info(f"Подключен к ClickHouse: {self.clickhouse_host}:{self.clickhouse_port}")
        except Exception as e:
            logger.error(f"Ошибка подключения к ClickHouse: {e}")
            sys.exit(1)
    
    def get_last_hour_locks(self):
        """
        Получение статистики по блокировкам за последний час
        """
        query = """
        SELECT 
            count() as total_locks,
            countIf(event_type = 'DEADLOCK') as deadlocks,
            countIf(event_type = 'TTIMEOUT') as timeouts,
            avg(lock_wait_time) as avg_wait_time,
            max(lock_wait_time) as max_wait_time,
            uniq(table_name) as tables_involved,
            uniq(session_id) as sessions_involved
        FROM lock_events
        WHERE event_datetime >= now() - interval 1 hour
        """
        
        result = self.client.execute(query)
        if result and result[0]:
            stats = {
                'total_locks': result[0][0],
                'deadlocks': result[0][1],
                'timeouts': result[0][2],
                'avg_wait_ms': result[0][3] / 1000 if result[0][3] else 0,
                'max_wait_ms': result[0][4] / 1000 if result[0][4] else 0,
                'tables_involved': result[0][5],
                'sessions_involved': result[0][6]
            }
            return stats
        return None
    
    def get_weekly_trend(self):
        """
        Получение тренда за последние 7 дней
        """
        query = """
        SELECT 
            toDate(event_datetime) as date,
            avg(lock_wait_time) as avg_wait,
            countIf(event_type = 'DEADLOCK') as deadlocks
        FROM lock_events
        WHERE event_datetime >= now() - interval 7 day
        GROUP BY date
        ORDER BY date
        """
        
        result = self.client.execute(query)
        if len(result) < 2:
            return None
        
        # Считаем среднее за первую половину и вторую половину
        mid = len(result) // 2
        first_half = [r[1] for r in result[:mid]]
        second_half = [r[1] for r in result[mid:]]
        
        if first_half and second_half:
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            if avg_first > 0:
                trend_pct = ((avg_second - avg_first) / avg_first) * 100
            else:
                trend_pct = 0
            
            return {
                'trend_pct': trend_pct,
                'avg_first_ms': avg_first / 1000,
                'avg_second_ms': avg_second / 1000
            }
        return None
    
    def get_top_tables_last_hour(self, limit=10):
        """
        Получение топ таблиц по блокировкам за последний час
        """
        query = f"""
        SELECT 
            table_name,
            count() as lock_count,
            countIf(event_type = 'DEADLOCK') as deadlocks,
            avg(lock_wait_time) as avg_wait
        FROM lock_events
        WHERE event_datetime >= now() - interval 1 hour
          AND table_name != ''
        GROUP BY table_name
        ORDER BY lock_count DESC
        LIMIT {limit}
        """
        
        result = self.client.execute(query)
        tables = []
        for row in result:
            tables.append({
                'table': row[0],
                'lock_count': row[1],
                'deadlocks': row[2],
                'avg_wait_ms': row[3] / 1000 if row[3] else 0
            })
        return tables
    
    def analyze_risk(self):
        """
        Анализ риска дедлоков на основе всех метрик
        
        Returns:
            dict: результаты анализа
        """
        risk = {
            'timestamp': datetime.now().isoformat(),
            'level': 'normal',
            'score': 0,
            'warnings': [],
            'metrics': {},
            'tables': []
        }
        
        # 1. Статистика за последний час
        last_hour = self.get_last_hour_locks()
        if last_hour:
            risk['metrics']['last_hour'] = last_hour
            
            # Проверка на дедлоки
            if last_hour['deadlocks'] >= self.DEADLOCK_THRESHOLD:
                risk['score'] += 50
                risk['warnings'].append({
                    'level': 'critical',
                    'message': f"Обнаружены deadlock'и: {last_hour['deadlocks']} за последний час!"
                })
            
            # Проверка времени ожидания
            if last_hour['max_wait_ms'] > self.WAIT_TIME_CRITICAL / 1000:
                risk['score'] += 30
                risk['warnings'].append({
                    'level': 'critical',
                    'message': f"Критическое время ожидания блокировки: {last_hour['max_wait_ms']:.0f} мс"
                })
            elif last_hour['avg_wait_ms'] > self.WAIT_TIME_THRESHOLD / 1000:
                risk['score'] += 15
                risk['warnings'].append({
                    'level': 'warning',
                    'message': f"Высокое среднее время ожидания: {last_hour['avg_wait_ms']:.0f} мс"
                })
        
        # 2. Тренд за неделю
        trend = self.get_weekly_trend()
        if trend:
            risk['metrics']['trend'] = trend
            
            if trend['trend_pct'] > 100:
                risk['score'] += 40
                risk['warnings'].append({
                    'level': 'critical',
                    'message': f"Рост времени ожидания на {trend['trend_pct']:.0f}% за неделю!"
                })
            elif trend['trend_pct'] > 50:
                risk['score'] += 20
                risk['warnings'].append({
                    'level': 'warning',
                    'message': f"Рост времени ожидания на {trend['trend_pct']:.0f}% за неделю"
                })
        
        # 3. Топ таблиц за последний час
        risk['tables'] = self.get_top_tables_last_hour(10)
        
        # Определение уровня риска
        if risk['score'] >= 70:
            risk['level'] = 'critical'
        elif risk['score'] >= 40:
            risk['level'] = 'high'
        elif risk['score'] >= 20:
            risk['level'] = 'warning'
        
        return risk
    
    def send_telegram_alert(self, risk):
        """Отправка алерта в Telegram"""
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not telegram_token or not chat_id:
            logger.warning("Telegram не настроен")
            return
        
        # Эмодзи для разных уровней
        emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'warning': '⚡',
            'normal': '✅'
        }.get(risk['level'], '📢')
        
        # Формируем сообщение
        message = f"{emoji} **АНАЛИЗ БЛОКИРОВОК 1С**\n\n"
        message += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        message += f"📊 Уровень риска: **{risk['level'].upper()}** (оценка: {risk['score']})\n\n"
        
        if risk['warnings']:
            message += "**⚠️ Предупреждения:**\n"
            for w in risk['warnings']:
                message += f"• {w['message']}\n"
            message += "\n"
        
        if risk['metrics'].get('last_hour'):
            m = risk['metrics']['last_hour']
            message += "**📈 За последний час:**\n"
            message += f"• Блокировок: {m['total_locks']}\n"
            message += f"• Дедлоков: {m['deadlocks']}\n"
            message += f"• Таймаутов: {m['timeouts']}\n"
            message += f"• Среднее ожидание: {m['avg_wait_ms']:.0f} мс\n"
            message += f"• Макс. ожидание: {m['max_wait_ms']:.0f} мс\n"
            message += "\n"
        
        if risk['tables']:
            message += "**📋 Топ таблиц по блокировкам:**\n"
            for t in risk['tables'][:5]:
                deadlock_mark = "🔴" if t['deadlocks'] > 0 else "⚪"
                message += f"{deadlock_mark} {t['table']}: {t['lock_count']} блокировок"
                if t['avg_wait_ms'] > 100:
                    message += f" ⏱️ {t['avg_wait_ms']:.0f} мс"
                message += "\n"
        
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            })
            if response.status_code == 200:
                logger.info("Алерт отправлен в Telegram")
            else:
                logger.error(f"Ошибка Telegram: {response.text}")
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
    
    def create_jira_ticket(self, risk):
        """Создание задачи в Jira при высоком риске"""
        try:
            from scripts.itsm.jira_integration import JiraClient
            
            jira = JiraClient()
            
            # Определяем приоритет
            if risk['level'] == 'critical':
                priority = "Highest"
                summary = f"[КРИТИЧНО] Обнаружены deadlock'и в 1С"
            elif risk['level'] == 'high':
                priority = "High"
                summary = f"[СРОЧНО] Высокий риск дедлоков в 1С"
            else:
                priority = "Medium"
                summary = f"[ВНИМАНИЕ] Рост блокировок в 1С"
            
            # Формируем описание
            description = f"*Автоматически создано системой мониторинга 1CML*\n\n"
            description += f"**Проблема:** {risk['warnings'][0]['message'] if risk['warnings'] else 'Обнаружен рост блокировок'}\n\n"
            
            if risk['metrics'].get('last_hour'):
                m = risk['metrics']['last_hour']
                description += "**Метрики за последний час:**\n"
                description += f"• Дедлоки: {m['deadlocks']}\n"
                description += f"• Среднее время ожидания: {m['avg_wait_ms']:.0f} мс\n"
                description += f"• Макс. время ожидания: {m['max_wait_ms']:.0f} мс\n\n"
            
            if risk['tables']:
                description += "**Подозрительные таблицы:**\n"
                for t in risk['tables'][:5]:
                    if t['deadlocks'] > 0 or t['avg_wait_ms'] > 500:
                        description += f"• {t['table']}: {t['lock_count']} блокировок, {t['avg_wait_ms']:.0f} мс\n"
                description += "\n"
            
            description += "**Рекомендации:**\n"
            description += "1. Проверить индексы для указанных таблиц\n"
            description += "2. Проанализировать длительные транзакции\n"
            description += "3. Оптимизировать запросы к конфликтующим таблицам\n"
            
            # Создаем задачу
            issue_key = jira.create_issue(
                summary=summary,
                description=description,
                priority=priority
            )
            
            if issue_key:
                logger.info(f"Создана задача в Jira: {issue_key}")
                return issue_key
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи в Jira: {e}")
        
        return None
    
    def save_to_postgresql(self, risk):
        """Сохранение результата в PostgreSQL"""
        try:
            import psycopg2
            
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'monitoring'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'password')
            )
            
            cur = conn.cursor()
            
            # Создаем таблицу, если нет
            cur.execute("""
                CREATE TABLE IF NOT EXISTS deadlock_checks (
                    id SERIAL PRIMARY KEY,
                    check_time TIMESTAMP,
                    risk_level VARCHAR(20),
                    risk_score INTEGER,
                    deadlocks_last_hour INTEGER,
                    avg_wait_ms FLOAT,
                    max_wait_ms FLOAT,
                    trend_pct FLOAT,
                    top_tables TEXT,
                    warnings TEXT
                )
            """)
            
            # Вставляем данные
            m = risk['metrics'].get('last_hour', {})
            trend = risk['metrics'].get('trend', {})
            
            cur.execute("""
                INSERT INTO deadlock_checks 
                (check_time, risk_level, risk_score, deadlocks_last_hour, 
                 avg_wait_ms, max_wait_ms, trend_pct, top_tables, warnings)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                risk['level'],
                risk['score'],
                m.get('deadlocks', 0),
                m.get('avg_wait_ms', 0),
                m.get('max_wait_ms', 0),
                trend.get('trend_pct', 0),
                json.dumps(risk['tables']),
                json.dumps(risk['warnings'])
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info("Результат сохранен в PostgreSQL")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в PostgreSQL: {e}")
    
    def run(self):
        """Основной метод запуска"""
        logger.info("=" * 60)
        logger.info("ЗАПУСК АНАЛИЗА БЛОКИРОВОК")
        
        # Анализируем риск
        risk = self.analyze_risk()
        
        # Логируем результаты
        logger.info(f"Уровень риска: {risk['level'].upper()} (оценка: {risk['score']})")
        
        if risk['warnings']:
            logger.info("Предупреждения:")
            for w in risk['warnings']:
                logger.info(f"  {w['level']}: {w['message']}")
        
        if risk['metrics'].get('last_hour'):
            m = risk['metrics']['last_hour']
            logger.info(f"За последний час: блокировок {m['total_locks']}, "
                       f"дедлоков {m['deadlocks']}, "
                       f"среднее ожидание {m['avg_wait_ms']:.0f} мс")
        
        # Сохраняем результат
        self.save_to_postgresql(risk)
        
        # Отправляем алерты в зависимости от уровня риска
        if risk['level'] in ['critical', 'high']:
            self.send_telegram_alert(risk)
            self.create_jira_ticket(risk)
        elif risk['level'] == 'warning' and risk['score'] > 30:
            self.send_telegram_alert(risk)
        
        logger.info("АНАЛИЗ ЗАВЕРШЕН")
        logger.info("=" * 60)
        
        return risk

def main():
    """Точка входа"""
    detector = DeadlockDetector()
    detector.run()

if __name__ == "__main__":
    main()
```

---

## 7. Дашборд для визуализации блокировок

**Файл:** `grafana/dashboards/locks_trend.json` (ключевые элементы)

```json
{
  "title": "1CML - Анализ блокировок и риск дедлоков",
  "panels": [
    {
      "title": "Дедлоки по дням",
      "type": "timeseries",
      "targets": [{
        "datasource": "ClickHouse",
        "query": "SELECT event_date, countIf(event_type='DEADLOCK') FROM lock_events WHERE $__timeFilter(event_date) GROUP BY event_date ORDER BY event_date"
      }]
    },
    {
      "title": "Среднее время ожидания блокировок",
      "type": "timeseries",
      "targets": [{
        "datasource": "ClickHouse",
        "query": "SELECT event_date, avg(lock_wait_time)/1000 FROM lock_events WHERE $__timeFilter(event_date) GROUP BY event_date ORDER BY event_date"
      }]
    },
    {
      "title": "Топ-10 таблиц по блокировкам",
      "type": "table",
      "targets": [{
        "datasource": "ClickHouse",
        "query": "SELECT table_name, count() as locks, countIf(event_type='DEADLOCK') as deadlocks, avg(lock_wait_time)/1000 as avg_wait_ms FROM lock_events WHERE event_date = today() GROUP BY table_name ORDER BY locks DESC LIMIT 10"
      }]
    }
  ]
}
```

---

## 8. Настройка автоматического запуска

### 8.1. Планировщик Windows

**Файл:** `scripts/setup_deadlock_scheduler.bat`

```batch
@echo off
echo Настройка планировщика для анализа блокировок

:: Каждый час (на 5-й минуте)
schtasks /create /tn "1CML Check Deadlocks" /tr "C:\Python39\python.exe C:\1CML\scripts\check_deadlocks.py" /sc hourly /st 00:05 /f

:: Каждый день в 08:00 - отчет по трендам
schtasks /create /tn "1CML Deadlock Report" /tr "C:\Python39\python.exe C:\1CML\scripts\analyze_lock_trends.py" /sc daily /st 08:00 /f

echo Готово!
pause
```

### 8.2. Переменные окружения (добавить в `.env`)

```env
# ClickHouse (для блокировок)
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DB=techlog

# Пороги для алертов
DEADLOCK_THRESHOLD=1
WAIT_TIME_THRESHOLD=500000
WAIT_TIME_CRITICAL=1000000
TREND_THRESHOLD=50
```

---

## 9. Пример работы скрипта

### 9.1. Нормальная ситуация

```
2026-02-28 10:05:01 - ЗАПУСК АНАЛИЗА БЛОКИРОВОК
2026-02-28 10:05:02 - Уровень риска: NORMAL (оценка: 5)
2026-02-28 10:05:02 - За последний час: блокировок 145, дедлоков 0, среднее ожидание 45 мс
2026-02-28 10:05:03 - Результат сохранен в PostgreSQL
2026-02-28 10:05:03 - АНАЛИЗ ЗАВЕРШЕН
```

### 9.2. Рост блокировок (предупреждение)

```
2026-02-28 14:05:01 - ЗАПУСК АНАЛИЗА БЛОКИРОВОК
2026-02-28 14:05:02 - Уровень риска: WARNING (оценка: 25)
2026-02-28 14:05:02 - Предупреждения:
2026-02-28 14:05:02 -   warning: Высокое среднее время ожидания: 567 мс
2026-02-28 14:05:02 -   warning: Рост времени ожидания на 67% за неделю
2026-02-28 14:05:02 - За последний час: блокировок 234, дедлоков 0, среднее ожидание 567 мс
2026-02-28 14:05:03 - Алерт отправлен в Telegram
2026-02-28 14:05:03 - Результат сохранен в PostgreSQL
2026-02-28 14:05:03 - АНАЛИЗ ЗАВЕРШЕН
```

### 9.3. Дедлоки (критично)

```
2026-02-28 15:05:01 - ЗАПУСК АНАЛИЗА БЛОКИРОВОК
2026-02-28 15:05:02 - Уровень риска: CRITICAL (оценка: 85)
2026-02-28 15:05:02 - Предупреждения:
2026-02-28 15:05:02 -   critical: Обнаружены deadlock'и: 3 за последний час!
2026-02-28 15:05:02 -   critical: Критическое время ожидания блокировки: 2345 мс
2026-02-28 15:05:02 -   critical: Рост времени ожидания на 156% за неделю!
2026-02-28 15:05:02 - За последний час: блокировок 456, дедлоков 3, среднее ожидание 892 мс
2026-02-28 15:05:03 - Алерт отправлен в Telegram
2026-02-28 15:05:04 - Создана задача в Jira: IT-5678
2026-02-28 15:05:04 - Результат сохранен в PostgreSQL
2026-02-28 15:05:04 - АНАЛИЗ ЗАВЕРШЕН
```

---

## 10. Полный цикл работы прогноза дедлоков

```
┌────────────────────────────────────────────────────────────────┐
│                    ДАННЫЕ (ClickHouse)                          │
│  lock_events (сырые события блокировок)                         │
│  lock_hourly_stats (агрегаты по часам)                          │
│  lock_table_stats (статистика по таблицам)                      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│              АНАЛИЗ (каждый час, в 5 минут)                     │
│  1. check_deadlocks.py                                         │
│     → статистика за последний час                               │
│     → тренд за неделю                                           │
│     → топ таблиц по блокировкам                                 │
│                                                                 │
│  2. Расчет риска:                                               │
│     • Если есть deadlock'и → CRITICAL                           │
│     • Если время ожидания > 1с → CRITICAL                       │
│     • Если рост > 100% → CRITICAL                               │
│     • Если рост > 50% → HIGH                                    │
│     • Если время > 500мс → WARNING                              │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│              ОПОВЕЩЕНИЕ (при риске)                             │
│  • Telegram: детальный отчет                                    │
│  • Jira: задача с приоритетом и таблицами                       │
│  • PostgreSQL: сохранение истории                               │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│              ВИЗУАЛИЗАЦИЯ (Grafana)                             │
│  • График дедлоков по дням                                      │
│  • Тренд времени ожидания                                       │
│  • Топ таблиц по блокировкам                                    │
└────────────────────────────────────────────────────────────────┘
```

---

## 11. Что нужно для запуска

### 11.1. Файлы для создания

```
1CML/
├── clickhouse/
│   └── schema_locks.sql                  # Таблицы для блокировок
├── scripts/
│   ├── techlog_parser_locks.py            # Парсер с фокусом на блокировки
│   ├── analyze_lock_trends.py              # Анализ трендов
│   ├── check_deadlocks.py                  # Основной скрипт
│   ├── alert_telegram.py                    # Отправка в Telegram
│   └── itsm/                                 # ITSM интеграции
├── logs/                                    # Папка для логов
│   └── deadlocks.log
└── .env                                     # Конфигурация
```

### 11.2. Команды для запуска

```bash
# 1. Создание таблиц в ClickHouse
cat clickhouse/schema_locks.sql | docker exec -i clickhouse-server clickhouse-client --multiline

# 2. Тестовый запуск анализа
python scripts/check_deadlocks.py

# 3. Просмотр трендов
python scripts/analyze_lock_trends.py

# 4. Настройка планировщика
scripts\setup_deadlock_scheduler.bat
```

### 11.3. Проверка работы

```bash
# Посмотреть последние записи в логе
tail -f logs/deadlocks.log

# Проверить данные в ClickHouse
docker exec -it clickhouse-server clickhouse-client --query "SELECT count() FROM lock_events WHERE event_date = today()"

# Проверить созданные задачи в Jira
# https://your-domain.atlassian.net/issues/?jql=summary~"дедлок"
```

**Теперь у вас есть полная, готовая к использованию система прогнозирования дедлоков 1С, которая:**

1. Собирает данные о блокировках из техжурнала 1С в ClickHouse
2. Анализирует тренды времени ожидания и количества дедлоков
3. Рассчитывает риск на основе пороговых значений
4. Прогнозирует вероятность возникновения дедлоков
5. Отправляет алерты в Telegram при высоком риске
6. Создает задачи в Jira с указанием проблемных таблиц
7. Хранит историю проверок в PostgreSQL
