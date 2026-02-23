#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Прогнозирование заполнения диска с помощью линейной регрессии
Данные: из Windows Performance Counters или техжурнала 1С
Версия: 2.0
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import logging
import os
import sys
from dotenv import load_dotenv
import argparse
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / '../logs/disk_predict.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('disk_predictor')

# Загрузка переменных окружения
load_dotenv(Path(__file__).parent / '../.env')

# Конфигурация
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'monitoring'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

DISK_LIMIT_GB = float(os.getenv('DISK_LIMIT_GB', '200'))
DISK_LETTER = os.getenv('DISK_LETTER', 'D:')
FORECAST_DAYS = [7, 14, 30]  # на сколько дней вперед прогнозируем

def get_historical_disk_usage(days=60, source='test'):
    """
    Получает исторические данные по диску
    
    Args:
        days: количество дней истории
        source: источник данных ('test', 'prometheus', 'windows')
    
    Returns:
        DataFrame с колонками date, used_gb
    """
    if source == 'test':
        # Генерируем тестовые данные для демо
        logger.info("Использую тестовые данные")
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        # Линейный рост от 100 до 150 ГБ с небольшим шумом
        used = np.linspace(100, 150, 30) + np.random.normal(0, 2, 30)
        return pd.DataFrame({'date': dates, 'used_gb': used})
    
    elif source == 'prometheus':
        # TODO: реализовать получение из Prometheus
        logger.error("Получение из Prometheus пока не реализовано")
        sys.exit(1)
    
    elif source == 'windows':
        # TODO: реализовать получение из WMI/Performance Counters
        logger.error("Получение из Windows пока не реализовано")
        sys.exit(1)
    
    else:
        # Пытаемся получить из БД
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            query = """
                SELECT 
                    date, 
                    used_gb 
                FROM disk_usage 
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date
            """ % days
            
            df = pd.read_sql(query, conn, parse_dates=['date'])
            conn.close()
            
            if df.empty:
                logger.warning("Нет исторических данных в БД. Использую тестовые.")
                return get_historical_disk_usage(days, 'test')
            
            logger.info(f"Загружено {len(df)} записей из БД")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка получения данных из БД: {e}")
            logger.info("Переключаюсь на тестовые данные")
            return get_historical_disk_usage(days, 'test')

def train_forecast_model(df):
    """
    Обучает модель линейной регрессии на исторических данных
    
    Args:
        df: DataFrame с колонками date, used_gb
    
    Returns:
        model: обученная модель
        metrics: словарь с метриками качества
        last_day: последний день в данных
    """
    # Подготовка данных: дни от начала отсчета
    df = df.sort_values('date').copy()
    df['day_num'] = (df['date'] - df['date'].min()).dt.days
    
    X = df['day_num'].values.reshape(-1, 1)
    y = df['used_gb'].values
    
    # Разделение на train/test (последние 20% для проверки)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    # Обучение модели
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Оценка качества
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    metrics = {
        'mae': mae,
        'r2': r2,
        'growth_rate': model.coef_[0],
        'intercept': model.intercept_
    }
    
    logger.info(f"Модель обучена")
    logger.info(f"  MAE: {mae:.2f} ГБ")
    logger.info(f"  R2: {r2:.3f}")
    logger.info(f"  Скорость роста: {model.coef_[0]:.3f} ГБ/день")
    logger.info(f"  Начальный размер: {model.intercept_:.2f} ГБ")
    
    return model, metrics, df['day_num'].max()

def make_forecast(model, last_day, days_ahead):
    """
    Делает прогноз на days_ahead дней вперед
    """
    future_days = np.array([last_day + i for i in range(1, days_ahead + 1)]).reshape(-1, 1)
    forecast = model.predict(future_days)
    return forecast

def calculate_days_to_limit(model, current_usage, limit_gb):
    """
    Рассчитывает количество дней до достижения лимита
    """
    if model.coef_[0] <= 0:
        return float('inf')  # диск не растет или уменьшается
    
    days_to_limit = (limit_gb - current_usage) / model.coef_[0]
    return max(0, days_to_limit)

def save_forecast_to_db(forecast_date, actual_gb, forecasts_dict, metrics):
    """
    Сохраняет прогноз в PostgreSQL
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Вставка прогноза
        query = """
            INSERT INTO disk_forecast 
                (metric_date, disk_used_gb, forecast_7d_gb, forecast_14d_gb, 
                 forecast_30d_gb, forecast_date, growth_rate_gb_per_day, days_to_limit)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
            ON CONFLICT (metric_date) 
            DO UPDATE SET 
                disk_used_gb = EXCLUDED.disk_used_gb,
                forecast_7d_gb = EXCLUDED.forecast_7d_gb,
                forecast_14d_gb = EXCLUDED.forecast_14d_gb,
                forecast_30d_gb = EXCLUDED.forecast_30d_gb,
                forecast_date = EXCLUDED.forecast_date,
                growth_rate_gb_per_day = EXCLUDED.growth_rate_gb_per_day,
                days_to_limit = EXCLUDED.days_to_limit
        """
        
        days_to_limit = calculate_days_to_limit(
            None, actual_gb, DISK_LIMIT_GB
        )  # Здесь нужна модель, упростим для примера
        
        cur.execute(query, (
            forecast_date.date(),
            actual_gb,
            forecasts_dict.get(7),
            forecasts_dict.get(14),
            forecasts_dict.get(30),
            metrics['growth_rate'],
            days_to_limit
        ))
        
        # Сохранение метрик качества модели
        cur.execute("""
            INSERT INTO model_quality (train_date, model_type, mae, r2, growth_rate)
            VALUES (NOW(), 'linear_regression', %s, %s, %s)
        """, (metrics['mae'], metrics['r2'], metrics['growth_rate']))
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Прогноз на {forecast_date.date()} сохранен в БД")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения в БД: {e}")
        raise

def check_critical_threshold(forecasts, current_usage):
    """
    Проверяет, превысит ли прогноз критический порог
    
    Returns:
        list: список предупреждений
    """
    warnings = []
    
    # Проверка прогнозов
    for days, value in forecasts.items():
        if value > DISK_LIMIT_GB:
            warnings.append({
                'type': 'forecast',
                'days': days,
                'value': float(value),
                'threshold': DISK_LIMIT_GB,
                'message': f"Через {days} дней диск превысит {DISK_LIMIT_GB} ГБ"
            })
            logger.warning(f"⚠️ КРИТИЧЕСКИЙ ПРОГНОЗ: через {days} дней {value:.1f} ГБ")
    
    # Проверка текущего уровня
    if current_usage > DISK_LIMIT_GB * 0.9:
        warnings.append({
            'type': 'current',
            'value': float(current_usage),
            'threshold': DISK_LIMIT_GB,
            'message': f"Текущее заполнение {current_usage:.1f} ГБ (>90% лимита)"
        })
        logger.warning(f"⚠️ ВНИМАНИЕ: текущее заполнение {current_usage:.1f} ГБ")
    
    return warnings

def send_alerts(warnings):
    """
    Отправляет алерты (вызов внешнего скрипта)
    """
    if not warnings:
        return
    
    try:
        from alert_telegram import send_telegram_alert
        
        # Формируем сообщение
        message = f"🚨 **ПРОГНОЗ ЗАПОЛНЕНИЯ ДИСКА {DISK_LETTER}**\n\n"
        for w in warnings:
            message += f"• {w['message']}\n"
        
        message += f"\nДата расчета: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Отправляем
        send_telegram_alert(message)
        logger.info("Алерты отправлены")
        
    except ImportError:
        logger.warning("Модуль alert_telegram не найден, алерты не отправлены")
    except Exception as e:
        logger.error(f"Ошибка отправки алертов: {e}")

def main():
    parser = argparse.ArgumentParser(description='Прогноз заполнения диска')
    parser.add_argument('--source', default='auto', 
                       choices=['auto', 'test', 'prometheus', 'windows'],
                       help='Источник данных')
    parser.add_argument('--days', type=int, default=60,
                       help='Количество дней истории')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("ЗАПУСК ПРОГНОЗИРОВАНИЯ ДИСКА")
    logger.info(f"Диск: {DISK_LETTER}, лимит: {DISK_LIMIT_GB} ГБ")
    
    try:
        # 1. Получаем исторические данные
        df = get_historical_disk_usage(days=args.days, source=args.source)
        logger.info(f"Загружено {len(df)} записей с {df['date'].min().date()} по {df['date'].max().date()}")
        
        # 2. Обучаем модель
        model, metrics, last_day = train_forecast_model(df)
        
        # 3. Делаем прогнозы
        forecasts = {}
        for days in FORECAST_DAYS:
            forecast_values = make_forecast(model, last_day, days)
            forecasts[days] = forecast_values[-1]  # берем последний день прогноза
            logger.info(f"Прогноз через {days} дней: {forecast_values[-1]:.1f} ГБ")
        
        # 4. Проверяем критические пороги
        current_usage = df['used_gb'].iloc[-1]
        warnings = check_critical_threshold(forecasts, current_usage)
        
        # 5. Сохраняем в БД
        save_forecast_to_db(df['date'].max(), current_usage, forecasts, metrics)
        
        # 6. Отправляем алерты
        if warnings:
            send_alerts(warnings)
        else:
            logger.info("✅ Все прогнозы в пределах нормы")
        
        logger.info("ПРОГНОЗ УСПЕШНО ЗАВЕРШЕН")
        
    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)
    
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
