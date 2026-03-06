Прогнозирование выхода новых версий платформы и конфигураций 1С

Идея для будущей реализации
Запуск: раз в месяц

📅 Прогноз выхода новых версий

┌─────────────────────────────────────────────────────────────────┐
│ Платформа 8.3.x                                                 │
│ Текущая версия: 8.3.23.1456 (05.06.2025)                        │
│ Следующий релиз: 8.3.24 (декабрь 2025)                          │
│ Доверительный интервал: ноябрь 2025 - январь 2026               │
├─────────────────────────────────────────────────────────────────┤
│ Конфигурация "Бухгалтерия"                                      │
│ Текущая версия: 3.0.150 (15.03.2025)                            │
│ Следующий релиз: 3.0.160 (июнь 2026)                            │
└─────────────────────────────────────────────────────────────────┘

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import logging
import requests
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReleasePredictor:
 
    Прогнозирование выхода новых версий
 
    
    def __init__(self):
        self.platform_releases = []
        self.config_releases = []
        self.models = {}
        
    def parse_releases_1c_ru(self):
      
        Парсинг сайта releases.1c.ru (в реальности нужен доступ)
      
        # TODO: реальный парсинг сайта
        # url = "https://releases.1c.ru/platform/history"
        # response = requests.get(url)
        # soup = BeautifulSoup(response.text, 'html.parser')
        pass
    
    def load_manual_history(self):
      
        Загрузка ручной истории релизов
       
        # Платформа
        self.platform_releases = [
            {'version': '8.3.10', 'date': '2017-06-15', 'type': 'major'},
            {'version': '8.3.11', 'date': '2018-03-22', 'type': 'major'},
            {'version': '8.3.12', 'date': '2018-11-29', 'type': 'major'},
            {'version': '8.3.13', 'date': '2019-06-20', 'type': 'major'},
            {'version': '8.3.14', 'date': '2020-02-13', 'type': 'major'},
            {'version': '8.3.15', 'date': '2020-09-24', 'type': 'major'},
            {'version': '8.3.16', 'date': '2021-04-22', 'type': 'major'},
            {'version': '8.3.17', 'date': '2021-11-18', 'type': 'major'},
            {'version': '8.3.18', 'date': '2022-06-16', 'type': 'major'},
            {'version': '8.3.19', 'date': '2023-02-16', 'type': 'major'},
            {'version': '8.3.20', 'date': '2023-09-28', 'type': 'major'},
            {'version': '8.3.21', 'date': '2024-04-25', 'type': 'major'},
            {'version': '8.3.22', 'date': '2024-11-14', 'type': 'major'},
            {'version': '8.3.23', 'date': '2025-06-05', 'type': 'major'},
        ]
        
        # Конфигурации
        self.config_releases = [
            {'version': '3.0.100', 'date': '2023-01-15', 'type': 'major'},
            {'version': '3.0.110', 'date': '2023-05-20', 'type': 'major'},
            {'version': '3.0.120', 'date': '2023-09-10', 'type': 'major'},
            {'version': '3.0.130', 'date': '2024-01-25', 'type': 'major'},
            {'version': '3.0.140', 'date': '2024-06-15', 'type': 'major'},
            {'version': '3.0.150', 'date': '2024-11-30', 'type': 'major'},
        ]
        
        logger.info(f"Загружено {len(self.platform_releases)} релизов платформы")
        logger.info(f"Загружено {len(self.config_releases)} релизов конфигураций")
        
    def analyze_release_patterns(self, releases):
      
        Анализ паттернов выхода релизов
      
        df = pd.DataFrame(releases)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Интервалы между релизами
        df['prev_date'] = df['date'].shift(1)
        df['interval_days'] = (df['date'] - df['prev_date']).dt.days
        
        # Статистика
        stats = {
            'count': len(df),
            'avg_interval': df['interval_days'].mean(),
            'std_interval': df['interval_days'].std(),
            'min_interval': df['interval_days'].min(),
            'max_interval': df['interval_days'].max(),
            'last_date': df['date'].iloc[-1],
            'last_version': df['version'].iloc[-1]
        }
        
        # Тренд (увеличиваются или уменьшаются интервалы)
        X = np.arange(len(df) - 1).reshape(-1, 1)
        y = df['interval_days'].dropna().values
        
        if len(y) > 3:
            model = LinearRegression()
            model.fit(X, y)
            stats['trend'] = model.coef_[0]  # положительный = интервалы растут
        
        return stats
    
    def predict_next_release(self, stats):
        
        Прогноз следующего релиза
        
        avg_interval = stats['avg_interval']
        std_interval = stats['std_interval']
        last_date = stats['last_date']
        
        # Прогноз даты
        next_date = last_date + timedelta(days=avg_interval)
        
        # Доверительный интервал
        lower_bound = last_date + timedelta(days=avg_interval - std_interval)
        upper_bound = last_date + timedelta(days=avg_interval + std_interval)
        
        # Извлечение следующей версии
        last_version = stats['last_version']
        version_parts = last_version.split('.')
        
        # Увеличение версии
        if len(version_parts) >= 3:
            major, minor, build = version_parts[:3]
            next_version = f"{major}.{minor}.{int(build) + 1}"
        else:
            next_version = "?.?.?"
        
        return {
            'next_version': next_version,
            'next_date': next_date,
            'confidence_low': lower_bound,
            'confidence_high': upper_bound,
            'probability': 0.85  # упрощенно
        }
    
    def generate_recommendations(self, platform_pred, config_pred):
        
        Генерация рекомендаций по планированию обновлений
        
        recommendations = []
        
        # Платформа
        days_to_release = (platform_pred['next_date'] - datetime.now()).days
        if days_to_release < 60:
            recommendations.append({
                'type': 'platform',
                'priority': 'high',
                'message': f"Подготовка к обновлению платформы до {platform_pred['next_version']}",
                'deadline': platform_pred['next_date'] - timedelta(days=30),
                'actions': [
                    "Создать тестовый контур",
                    "Провести полное тестирование",
                    "Обновить продуктив после выхода первого патча"
                ]
            })
        
        # Конфигурация
        days_to_release = (config_pred['next_date'] - datetime.now()).days
        if days_to_release < 90:
            recommendations.append({
                'type': 'config',
                'priority': 'medium',
                'message': f"Планирование обновления конфигурации до {config_pred['next_version']}",
                'deadline': config_pred['next_date'] - timedelta(days=45),
                'actions': [
                    "Изучить список изменений",
                    "Тестирование на копии базы",
                    "Обновление после выхода"
                ]
            })
        
        return recommendations
    
    def run_analysis(self):
        
        Полный анализ и прогноз
        
        # Загрузка данных
        self.load_manual_history()
        
        # Анализ платформы
        platform_stats = self.analyze_release_patterns(self.platform_releases)
        platform_pred = self.predict_next_release(platform_stats)
        
        logger.info(f"\nПлатформа:")
        logger.info(f"  Средний интервал: {platform_stats['avg_interval']:.0f} дней")
        logger.info(f"  Последняя версия: {platform_stats['last_version']}")
        logger.info(f"  Следующая: {platform_pred['next_version']} "
                   f"({platform_pred['next_date'].strftime('%Y-%m')})")
        
        # Анализ конфигураций
        config_stats = self.analyze_release_patterns(self.config_releases)
        config_pred = self.predict_next_release(config_stats)
        
        logger.info(f"\nКонфигурация:")
        logger.info(f"  Средний интервал: {config_stats['avg_interval']:.0f} дней")
        logger.info(f"  Последняя версия: {config_stats['last_version']}")
        logger.info(f"  Следующая: {config_pred['next_version']} "
                   f"({config_pred['next_date'].strftime('%Y-%m')})")
        
        # Рекомендации
        recommendations = self.generate_recommendations(platform_pred, config_pred)
        
        return {
            'platform': {
                'stats': platform_stats,
                'prediction': platform_pred
            },
            'config': {
                'stats': config_stats,
                'prediction': config_pred
            },
            'recommendations': recommendations
        }


def main():
  
    Точка входа для тестирования
  
    predictor = ReleasePredictor()
    results = predictor.run_analysis()
    
    logger.info("\n📋 Рекомендации:")
    for rec in results['recommendations']:
        logger.info(f"  {rec['priority'].upper()}: {rec['message']}")
        for action in rec['actions']:
            logger.info(f"    • {action}")


if __name__ == "__main__":
    main()
