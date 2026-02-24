#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки риска дедлоков на основе анализа техжурнала из ClickHouse
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
    
    def get_lock_stats(self, days=7):
        """
        Получение статистики по блокировкам за последние N дней
        
        Args:
            days: количество дней для анализа
            
        Returns:
            DataFrame с колонками: date, avg_lock_time, max_lock_time, 
            long_locks_count, deadlock_count
        """
        query = f"""
        SELECT 
            toDate(event_date) as date,
            avg(lock_time) as avg_lock_time,
            max(lock_time) as max_lock_time,
            countIf(lock_time > 1000000) as long_locks_count,
            countIf(position(lower(raw_line), 'deadlock') > 0) as deadlock_count,
            countIf(position(lower(raw_line), 'lock') > 0) as lock_events
        FROM techlog
        WHERE event_date >= today() - {days}
          AND lock_time > 0
        GROUP BY date
        ORDER BY date DESC
        """
        
        try:
            result = self.client.execute(query)
            df = pd.DataFrame(result, columns=[
                'date', 'avg_lock_time', 'max_lock_time', 
                'long_locks_count', 'deadlock_count', 'lock_events'
            ])
            logger.info(f"Получены данные за {len(df)} дней")
            return df
        except Exception as e:
            logger.error(f"Ошибка запроса к ClickHouse: {e}")
            return pd.DataFrame()
    
    def get_top_tables(self, days=1):
        """
        Получение топ-10 таблиц по блокировкам за последний день
        
        Returns:
            DataFrame с колонками: table, lock_count, avg_lock_time
        """
        query = f"""
        SELECT 
            extract(raw_line, 'table=\'([^\']*)\'') as table_name,
            count() as lock_count,
            avg(lock_time) as avg_lock_time,
            max(lock_time) as max_lock_time
        FROM techlog
        WHERE event_date = today()
          AND lock_time > 0
          AND table_name != ''
        GROUP BY table_name
        ORDER BY lock_count DESC
        LIMIT 10
        """
        
        try:
            result = self.client.execute(query)
            df = pd.DataFrame(result, columns=[
                'table_name', 'lock_count', 'avg_lock_time', 'max_lock_time'
            ])
            return df
        except Exception as e:
            logger.error(f"Ошибка запроса топ-таблиц: {e}")
            return pd.DataFrame()
    
    def calculate_trend(self, df):
        """
        Расчет тренда роста блокировок
        
        Args:
            df: DataFrame со статистикой по дням
            
        Returns:
            dict: метрики тренда
        """
        if len(df) < 3:
            return {
                'trend_percent': 0,
                'risk_level': 'unknown',
                'message': 'Недостаточно данных'
            }
        
        # Сортируем по дате (от старых к новым)
        df_sorted = df.sort_values('date')
        
        # Берем первую половину (базовый уровень) и вторую половину (текущий)
        mid = len(df_sorted) // 2
        base_avg = df_sorted.iloc[:mid]['avg_lock_time'].mean()
        current_avg = df_sorted.iloc[mid:]['avg_lock_time'].mean()
        
        if base_avg == 0:
            trend_percent = 0
        else:
            trend_percent = ((current_avg - base_avg) / base_avg) * 100
        
        # Определяем уровень риска
        if df_sorted['deadlock_count'].iloc[-1] > 0:
            risk_level = 'critical'
            message = f"⚠️ Обнаружены deadlock'и за последний день!"
        elif trend_percent > 100:
            risk_level = 'critical'
            message = f"🚨 Рост блокировок > 100% за период!"
        elif trend_percent > 50:
            risk_level = 'high'
            message = f"⚠️ Рост блокировок > 50% за период"
        elif trend_percent > 30:
            risk_level = 'warning'
            message = f"⚡ Рост блокировок > 30% за период"
        elif trend_percent > 10:
            risk_level = 'info'
            message = f"📈 Небольшой рост блокировок"
        else:
            risk_level = 'normal'
            message = f"✅ Блокировки в норме"
        
        # Добавляем информацию о долгих блокировках
        long_locks_today = df_sorted.iloc[-1]['long_locks_count'] if len(df_sorted) > 0 else 0
        if long_locks_today > 10:
            message += f" Долгих блокировок сегодня: {long_locks_today}"
        
        return {
            'trend_percent': round(trend_percent, 1),
            'base_avg': round(base_avg, 0),
            'current_avg': round(current_avg, 0),
            'risk_level': risk_level,
            'message': message,
            'deadlocks_today': int(df_sorted.iloc[-1]['deadlock_count']) if len(df_sorted) > 0 else 0,
            'long_locks_today': int(long_locks_today)
        }
    
    def send_telegram_alert(self, message, risk_level):
        """Отправка алерта в Telegram"""
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not telegram_token or not chat_id:
            logger.warning("Telegram не настроен, пропускаем отправку")
            return
        
        # Эмодзи в зависимости от уровня риска
        emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'warning': '⚡',
            'info': '📊',
            'normal': '✅',
            'unknown': '❓'
        }.get(risk_level, '📢')
        
        full_message = f"{emoji} **Анализ блокировок**\n\n{message}\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            requests.post(url, json={
                'chat_id': chat_id,
                'text': full_message,
                'parse_mode': 'Markdown'
            })
            logger.info("Алерт отправлен в Telegram")
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
    
    def create_jira_ticket(self, trend_data, top_tables):
        """Создание задачи в Jira при высоком риске"""
        try:
            # Добавляем путь к ITSM модулю
            sys.path.append(os.path.join(os.path.dirname(__file__), 'itsm'))
            from jira_integration import JiraClient
            
            jira = JiraClient()
            
            # Формируем заголовок
            if trend_data['deadlocks_today'] > 0:
                summary = f"[КРИТИЧНО] Обнаружены deadlock'и в базе 1С"
            else:
                summary = f"[Превентивно] Рост блокировок {trend_data['trend_percent']}% за неделю"
            
            # Формируем описание
            description = f"""
*Автоматически создано системой анализа блокировок 1CML*

**Проблема:** {trend_data['message']}

**Метрики за неделю:**
- Среднее время блокировки (текущее): {trend_data['current_avg']} мкс
- Среднее время блокировки (базовое): {trend_data['base_avg']} мкс
- Рост: {trend_data['trend_percent']}%
- Deadlock'и сегодня: {trend_data['deadlocks_today']}
- Долгих блокировок (>1с): {trend_data['long_locks_today']}

**Топ-5 таблиц по блокировкам сегодня:**
"""
            for _, row in top_tables.head(5).iterrows():
                description += f"- {row['table_name']}: {row['lock_count']} блокировок, среднее {row['avg_lock_time']} мкс\n"
            
            description += f"""
**Рекомендации:**
1. Проверить запросы к таблицам выше
2. Оптимизировать индексы
3. Проанализировать длительные транзакции

**Ссылки:**
- Дашборд: http://grafana:3000/d/locks-trend
- Лог: /var/log/1cml/deadlocks.log

*Создано: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
            
            # Определяем приоритет
            if trend_data['risk_level'] == 'critical':
                priority = "Highest"
            elif trend_data['risk_level'] == 'high':
                priority = "High"
            else:
                priority = "Medium"
            
            # Создаем задачу
            issue_key = jira.create_issue(
                summary=summary,
                description=description,
                priority=priority
            )
            
            if issue_key:
                logger.info(f"✅ Создана задача в Jira: {issue_key}")
                return issue_key
            else:
                logger.error("❌ Ошибка создания задачи в Jira")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка создания задачи в Jira: {e}")
            return None
    
    def run(self):
        """Основной метод запуска"""
        logger.info("=" * 60)
        logger.info("ЗАПУСК АНАЛИЗА БЛОКИРОВОК")
        
        # Получаем статистику за 7 дней
        df = self.get_lock_stats(days=7)
        
        if df.empty:
            logger.warning("Нет данных для анализа")
            return
        
        # Получаем топ таблиц за сегодня
        top_tables = self.get_top_tables()
        
        # Рассчитываем тренд
        trend = self.calculate_trend(df)
        
        # Выводим результаты
        logger.info(f"Результаты анализа:")
        logger.info(f"  Тренд: {trend['trend_percent']}%")
        logger.info(f"  Уровень риска: {trend['risk_level']}")
        logger.info(f"  {trend['message']}")
        
        if not top_tables.empty:
            logger.info(f"Топ таблиц по блокировкам сегодня:")
            for _, row in top_tables.iterrows():
                logger.info(f"  {row['table_name']}: {row['lock_count']} блокировок")
        
        # Отправляем алерт в Telegram при любом уровне кроме normal
        if trend['risk_level'] != 'normal':
            self.send_telegram_alert(trend['message'], trend['risk_level'])
        
        # Создаем задачу в Jira при critical или high
        if trend['risk_level'] in ['critical', 'high']:
            self.create_jira_ticket(trend, top_tables)
        
        # Если есть deadlock'и - всегда critical
        if trend['deadlocks_today'] > 0:
            self.send_telegram_alert(
                f"🚨 Обнаружены deadlock'и! Количество: {trend['deadlocks_today']}",
                'critical'
            )
            self.create_jira_ticket(trend, top_tables)
        
        logger.info("АНАЛИЗ ЗАВЕРШЕН")
        logger.info("=" * 60)


def main():
    """Точка входа"""
    detector = DeadlockDetector()
    detector.run()


if __name__ == "__main__":
    main()
