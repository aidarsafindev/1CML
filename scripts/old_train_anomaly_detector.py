#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Обучение модели для обнаружения аномалий в активности пользователей
Использует Isolation Forest для выявления выбросов
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import psycopg2
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('anomaly_trainer')

class AnomalyDetector:
    """Детектор аномалий на основе Isolation Forest"""
    
    def __init__(self, contamination=0.05, random_state=42):
        """
        Инициализация детектора
        
        Args:
            contamination: ожидаемая доля аномалий
            random_state: для воспроизводимости
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100,
            max_samples='auto',
            bootstrap=False
        )
        self.scaler = StandardScaler()
        self.feature_names = None
        
    def prepare_features(self, df):
        """
        Подготовка признаков для обучения
        
        Args:
            df: DataFrame с сырыми данными
        
        Returns:
            DataFrame с признаками
        """
        # Группируем по часам
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
        
        features = df.groupby(['timestamp', 'hour', 'day_of_week']).agg({
            'session_count': 'sum',
            'avg_duration': 'mean',
            'lock_count': 'sum',
            'avg_lock_time': 'mean',
            'error_count': 'sum'
        }).reset_index()
        
        # Добавляем скользящие средние
        for col in ['session_count', 'avg_duration', 'lock_count']:
            features[f'{col}_ma_7'] = features[col].rolling(7, min_periods=1).mean()
            features[f'{col}_ma_24'] = features[col].rolling(24, min_periods=1).mean()
        
        # Добавляем отклонения
        features['session_count_diff'] = features['session_count'] - features['session_count_ma_24']
        
        self.feature_names = [col for col in features.columns 
                              if col not in ['timestamp', 'hour', 'day_of_week']]
        
        return features
    
    def train(self, df_features):
        """
        Обучение модели
        
        Args:
            df_features: DataFrame с признаками
        """
        X = df_features[self.feature_names].fillna(0).values
        X_scaled = self.scaler.fit_transform(X)
        
        self.model.fit(X_scaled)
        
        # Оценка
        scores = self.model.decision_function(X_scaled)
        predictions = self.model.predict(X_scaled)
        
        n_anomalies = sum(predictions == -1)
        logger.info(f"Модель обучена. Найдено аномалий: {n_anomalies} ({n_anomalies/len(X)*100:.1f}%)")
        
        return predictions, scores
    
    def predict(self, features):
        """
        Предсказание для новых данных
        
        Args:
            features: DataFrame с признаками
        
        Returns:
            predictions: -1 (аномалия) или 1 (норма)
            scores: оценка аномальности
        """
        X = features[self.feature_names].fillna(0).values
        X_scaled = self.scaler.transform(X)
        
        predictions = self.model.predict(X_scaled)
        scores = self.model.decision_function(X_scaled)
        
        return predictions, scores
    
    def save_model(self, path):
        """
        Сохранение модели
        """
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }
        joblib.dump(model_data, path)
        logger.info(f"Модель сохранена в {path}")
    
    def load_model(self, path):
        """
        Загрузка модели
        """
        model_data = joblib.load(path)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        logger.info(f"Модель загружена из {path}")

def load_training_data(days=30, db_config=None):
    """
    Загрузка данных для обучения из PostgreSQL
    
    Args:
        days: количество дней истории
        db_config: конфигурация БД
    
    Returns:
        DataFrame с данными
    """
    if db_config is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'monitoring'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password')
        }
    
    try:
        conn = psycopg2.connect(**db_config)
        
        query = """
            SELECT 
                date_trunc('hour', event_time) as timestamp,
                COUNT(DISTINCT session_id) as session_count,
                AVG(duration) as avg_duration,
                COUNT(CASE WHEN lock_time > 0 THEN 1 END) as lock_count,
                AVG(lock_time) as avg_lock_time,
                COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as error_count
            FROM session_metrics
            WHERE event_time >= NOW() - INTERVAL '%s days'
            GROUP BY date_trunc('hour', event_time)
            ORDER BY timestamp
        """ % days
        
        df = pd.read_sql(query, conn, parse_dates=['timestamp'])
        conn.close()
        
        if df.empty:
            logger.warning("Нет данных в БД, генерируем тестовые")
            return generate_test_data(days)
        
        logger.info(f"Загружено {len(df)} записей из БД")
        return df
        
    except Exception as e:
        logger.error(f"Ошибка загрузки из БД: {e}")
        logger.info("Генерируем тестовые данные")
        return generate_test_data(days)

def generate_test_data(days=30):
    """
    Генерация тестовых данных для демо
    """
    logger.info("Генерация тестовых данных")
    
    timestamps = pd.date_range(
        end=datetime.now(),
        periods=days * 24,
        freq='H'
    )
    
    # Нормальный паттерн: больше днем, меньше ночью
    hour_of_day = timestamps.hour
    base_sessions = np.where(
        (hour_of_day >= 9) & (hour_of_day <= 18),
        100 + np.random.normal(0, 10, len(timestamps)),  # днем
        20 + np.random.normal(0, 5, len(timestamps))      # ночью
    )
    
    # Добавляем аномалии
    anomaly_indices = np.random.choice(len(timestamps), size=int(len(timestamps)*0.03), replace=False)
    base_sessions[anomaly_indices] = base_sessions[anomaly_indices] * 0.3  # резкое падение
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'session_count': base_sessions,
        'avg_duration': np.random.normal(1000, 200, len(timestamps)),
        'lock_count': np.random.poisson(5, len(timestamps)),
        'avg_lock_time': np.random.exponential(50, len(timestamps)),
        'error_count': np.random.poisson(1, len(timestamps))
    })
    
    return df

def main():
    parser = argparse.ArgumentParser(description='Обучение детектора аномалий')
    parser.add_argument('--days', type=int, default=30, help='Дней истории для обучения')
    parser.add_argument('--contamination', type=float, default=0.05, help='Доля аномалий')
    parser.add_argument('--output', default='models/anomaly_model.pkl', help='Путь для сохранения модели')
    parser.add_argument('--test', action='store_true', help='Режим тестирования')
    
    args = parser.parse_args()
    
    # Создаем директорию для моделей
    Path('models').mkdir(exist_ok=True)
    
    # Загружаем данные
    df = load_training_data(days=args.days)
    
    # Создаем и обучаем детектор
    detector = AnomalyDetector(contamination=args.contamination)
    features = detector.prepare_features(df)
    
    # Обучаем
    predictions, scores = detector.train(features)
    
    # Добавляем результаты в DataFrame
    features['prediction'] = predictions
    features['anomaly_score'] = scores
    
    # Анализ результатов
    anomalies = features[features['prediction'] == -1]
    logger.info(f"\nНайдено аномалий: {len(anomalies)}")
    
    if not anomalies.empty:
        logger.info("\nТоп-5 аномалий:")
        logger.info(anomalies.nlargest(5, 'anomaly_score')[['timestamp', 'session_count', 
                                                           'lock_count', 'anomaly_score']])
    
    # Сохраняем модель
    detector.save_model(args.output)
    
    # Тестирование на новых данных
    if args.test:
        logger.info("\nТестирование на новых данных...")
        test_df = generate_test_data(days=7)
        test_features = detector.prepare_features(test_df)
        test_pred, test_scores = detector.predict(test_features)
        
        test_anomalies = sum(test_pred == -1)
        logger.info(f"Найдено аномалий в тесте: {test_anomalies} ({test_anomalies/len(test_pred)*100:.1f}%)")

if __name__ == "__main__":
    main()
