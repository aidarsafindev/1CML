### `lock_prediction.md`

# Прогноз дедлоков

**Файл:** `scripts/locks/check_deadlocks.py`

Компонент для анализа блокировок и прогнозирования риска дедлоков. Запускается каждый час.

---

## 1. Получение статистики за последний час

```python
def get_last_hour_locks(self) -> dict:
    """
    Получение статистики по блокировкам за последний час
    """
    query = """
    SELECT 
        count() as total_locks,
        countIf(event_type = 'DEADLOCK') as deadlocks,
        countIf(event_type = 'TTIMEOUT') as timeouts,
        avg(lock_wait_time) as avg_wait,
        max(lock_wait_time) as max_wait,
        uniq(table_name) as tables_involved
    FROM lock_events
    WHERE event_datetime >= now() - interval 1 hour
    """
    
    result = self.client.execute(query)
    
    if result and result[0]:
        return {
            'total_locks': result[0][0],
            'deadlocks': result[0][1],
            'timeouts': result[0][2],
            'avg_wait_ms': result[0][3] / 1000 if result[0][3] else 0,
            'max_wait_ms': result[0][4] / 1000 if result[0][4] else 0,
            'tables_involved': result[0][5]
        }
    return {}
```

**Что делает:**
- Запрашивает из ClickHouse статистику за последний час
- Считает общее количество блокировок, дедлоков, таймаутов
- Переводит время ожидания из микросекунд в миллисекунды

**Пример результата:**
```python
{
    'total_locks': 1245,
    'deadlocks': 3,
    'timeouts': 15,
    'avg_wait_ms': 892,
    'max_wait_ms': 2345,
    'tables_involved': 23
}
```

---

## 2. Анализ тренда за неделю

```python
def get_weekly_trend(self) -> dict:
    """
    Расчет тренда времени ожидания за неделю
    """
    query = """
    SELECT 
        toDate(event_datetime) as date,
        avg(lock_wait_time) as avg_wait
    FROM lock_events
    WHERE event_datetime >= now() - interval 7 day
    GROUP BY date
    ORDER BY date
    """
    
    result = self.client.execute(query)
    
    if len(result) < 4:  # нужно минимум 4 дня
        return {'trend_pct': 0}
    
    # Берем первую половину (первые 3 дня)
    first_half = [r[1] for r in result[:3]]
    # Берем вторую половину (последние 3 дня)
    second_half = [r[1] for r in result[-3:]]
    
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    
    if avg_first == 0:
        trend = 0
    else:
        trend = (avg_second - avg_first) / avg_first * 100
    
    return {
        'trend_pct': round(trend, 1),
        'avg_first_ms': avg_first / 1000,
        'avg_second_ms': avg_second / 1000
    }
```

**Что делает:**
- Получает данные за последние 7 дней
- Сравнивает первую и вторую половину недели
- Считает процент роста времени ожидания

**Пример расчета:**
```
avg_first = (340 + 356 + 367) / 3 = 354 мс
avg_second = (567 + 745 + 892) / 3 = 735 мс
trend = (735 - 354) / 354 * 100 = 107% роста
```

---

## 3. Получение топ таблиц

```python
def get_top_tables_last_hour(self, limit=10) -> list:
    """
    Получение таблиц с наибольшим количеством блокировок
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
```

**Что делает:**
- Группирует блокировки по таблицам
- Сортирует по убыванию количества блокировок
- Возвращает топ таблиц с проблемами

**Пример результата:**
```python
[
    {'table': '_InfoRg12345', 'lock_count': 245, 'deadlocks': 2, 'avg_wait_ms': 892},
    {'table': '_AccumRg6789', 'lock_count': 187, 'deadlocks': 1, 'avg_wait_ms': 745},
    {'table': '_DocumentHeader', 'lock_count': 156, 'deadlocks': 0, 'avg_wait_ms': 567}
]
```

---

## 4. Расчет риска (score)

```python
def analyze_risk(self) -> dict:
    """
    Анализ риска и расчет score
    """
    stats = self.get_last_hour_locks()
    trend = self.get_weekly_trend()
    tables = self.get_top_tables_last_hour(5)
    
    score = 0
    warnings = []
    
    # 4.1. Проверка дедлоков
    if stats['deadlocks'] > 0:
        score += 50
        warnings.append(f"🚨 Обнаружены deadlock'и: {stats['deadlocks']} за час")
    
    # 4.2. Проверка времени ожидания
    if stats['avg_wait_ms'] > 1000:  # > 1 секунды
        score += 30
        warnings.append(f"⚠️ Критическое время ожидания: {stats['avg_wait_ms']:.0f} мс")
    elif stats['avg_wait_ms'] > 500:  # > 500 мс
        score += 15
        warnings.append(f"⚡ Высокое время ожидания: {stats['avg_wait_ms']:.0f} мс")
    
    # 4.3. Проверка тренда
    if trend['trend_pct'] > 100:
        score += 40
        warnings.append(f"📈 Рост > 100% за неделю ({trend['trend_pct']:.0f}%)")
    elif trend['trend_pct'] > 50:
        score += 20
        warnings.append(f"📈 Рост > 50% за неделю ({trend['trend_pct']:.0f}%)")
    
    # 4.4. Проверка таймаутов
    if stats['timeouts'] > 10:
        score += 10
        warnings.append(f"⏱️ Много таймаутов: {stats['timeouts']} за час")
    
    # Определение уровня риска
    if score >= 70:
        level = 'critical'
    elif score >= 40:
        level = 'high'
    elif score >= 20:
        level = 'warning'
    else:
        level = 'normal'
    
    return {
        'score': score,
        'level': level,
        'warnings': warnings,
        'stats': stats,
        'trend': trend,
        'tables': tables
    }
```

**Что делает:**
- Собирает все метрики
- Добавляет баллы за каждый проблемный показатель
- Определяет итоговый уровень риска

**Пример расчета:**
```
deadlocks = 3 → +50
avg_wait = 892 мс → +15
trend = 107% → +40
timeouts = 15 → +10
score = 115 → CRITICAL
```

---

## 5. Отправка уведомления в Telegram

```python
def send_telegram_alert(self, risk: dict):
    """
    Отправка результатов анализа в Telegram
    """
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    emoji = {
        'critical': '🔴',
        'high': '🟠',
        'warning': '🟡',
        'normal': '🟢'
    }.get(risk['level'], '📢')
    
    # Формирование сообщения
    message = f"{emoji} **АНАЛИЗ БЛОКИРОВОК**\n\n"
    message += f"📊 **За последний час:**\n"
    message += f"• Дедлоки: {risk['stats']['deadlocks']}\n"
    message += f"• Среднее ожидание: {risk['stats']['avg_wait_ms']:.0f} мс\n"
    message += f"• Таймауты: {risk['stats']['timeouts']}\n\n"
    
    if risk['trend']['trend_pct'] > 0:
        message += f"📈 **Тренд за неделю:** +{risk['trend']['trend_pct']}%\n\n"
    
    if risk['tables']:
        message += f"📋 **Топ таблиц:**\n"
        for t in risk['tables'][:3]:
            deadlock_mark = "🔴" if t['deadlocks'] > 0 else "⚪"
            message += f"{deadlock_mark} {t['table']}: {t['lock_count']} блок."
            if t['deadlocks'] > 0:
                message += f" (deadlock: {t['deadlocks']})"
            message += "\n"
    
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    )
```

**Что делает:**
- Формирует читаемое сообщение с эмодзи
- Добавляет ключевые метрики и топ таблиц
- Отправляет в Telegram

**Пример сообщения:**
```
🔴 **АНАЛИЗ БЛОКИРОВОК**

📊 **За последний час:**
• Дедлоки: 3
• Среднее ожидание: 892 мс
• Таймауты: 15

📈 **Тренд за неделю:** +107%

📋 **Топ таблиц:**
🔴 _InfoRg12345: 245 блок. (deadlock: 2)
🔴 _AccumRg6789: 187 блок. (deadlock: 1)
⚪ _DocumentHeader: 156 блок.
```

---

## 6. Создание задачи в Jira

```python
def create_jira_ticket(self, risk: dict):
    """
    Создание задачи в Jira при высоком риске
    """
    from scripts.itsm.jira_integration import JiraClient
    
    jira = JiraClient()
    
    # Определяем приоритет
    if risk['level'] == 'critical':
        priority = "Highest"
        summary = "[КРИТИЧНО] Обнаружены deadlock'и в 1С"
    elif risk['level'] == 'high':
        priority = "High"
        summary = "[СРОЧНО] Высокий риск дедлоков в 1С"
    else:
        priority = "Medium"
        summary = "[ВНИМАНИЕ] Рост блокировок в 1С"
    
    # Формируем описание
    description = f"""
    *Автоматически создано системой мониторинга*
    
    **Проблема:** {risk['warnings'][0]['message'] if risk['warnings'] else 'Рост блокировок'}
    
    **Метрики за последний час:**
    • Дедлоки: {risk['stats']['deadlocks']}
    • Среднее ожидание: {risk['stats']['avg_wait_ms']:.0f} мс
    • Таймауты: {risk['stats']['timeouts']}
    
    **Тренд за неделю:** +{risk['trend']['trend_pct']}%
    
    **Подозрительные таблицы:**
    """
    
    for t in risk['tables'][:3]:
        description += f"• {t['table']}: {t['lock_count']} блок."
        if t['deadlocks'] > 0:
            description += f" (deadlock: {t['deadlocks']})"
        description += "\n"
    
    # Создаем задачу
    issue_key = jira.create_issue(
        summary=summary,
        description=description,
        priority=priority
    )
    
    return issue_key
```

**Что делает:**
- Подключается к Jira через API
- Создает задачу с приоритетом в зависимости от уровня риска
- Добавляет в описание все метрики и проблемные таблицы

---

## 7. Полный цикл работы

```python
def run(self):
    """
    Основной метод запуска
    """
    logger.info("=" * 60)
    logger.info("ЗАПУСК АНАЛИЗА БЛОКИРОВОК")
    
    # Анализ риска
    risk = self.analyze_risk()
    
    # Логирование результатов
    logger.info(f"Уровень риска: {risk['level'].upper()} (оценка: {risk['score']})")
    
    for w in risk['warnings']:
        logger.warning(w)
    
    # Сохранение в БД
    self.save_to_postgresql(risk)
    
    # Отправка алертов
    if risk['level'] in ['critical', 'high']:
        self.send_telegram_alert(risk)
        ticket = self.create_jira_ticket(risk)
        logger.info(f"Создана задача в Jira: {ticket}")
    elif risk['level'] == 'warning':
        self.send_telegram_alert(risk)
    
    logger.info("АНАЛИЗ ЗАВЕРШЕН")
    logger.info("=" * 60)
```

**Что делает:**
- Запускает все шаги последовательно
- Логирует результаты
- Отправляет уведомления в зависимости от уровня риска

---

## Параметры для настройки

В файле `.env`:

```env
# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DB=techlog

# Telegram
TELEGRAM_TOKEN=1234567890:ABCdefGHIjkl
TELEGRAM_CHAT_ID=-123456789

# Jira
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=user@example.com
JIRA_API_TOKEN=token
JIRA_PROJECT_KEY=IT

# Пороги
DEADLOCK_THRESHOLD=1
WAIT_TIME_WARNING=500
WAIT_TIME_CRITICAL=1000
TREND_WARNING=50
TREND_CRITICAL=100
TIMEOUT_THRESHOLD=10
```

---

