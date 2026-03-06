Поиск оптимальных настроек кластера 1С и СУБД

Идея для будущей реализации
Запуск: по требованию или раз в квартал


⚙️ Оптимальные настройки для вашей инфраструктуры

┌─────────────────────────────────────────────────────────────────┐
│ Параметр          | Текущее | Оптимальное | Изменение | Эффект  │
│───────────────────|─────────|─────────────|───────────|──────── │
│ RAS процессов     | 2       | 3           | +50%      | +8%     │
│ RMNG процессов    | 4       | 6           | +50%      | +15%    │
│ RPHOST процессов  | 8       | 6           | -25%      | +12%    │
│ Разделяемая память| 4 ГБ    | 8 ГБ        | +100%     | +18%    │
│ Кэш СУБД          | 1 ГБ    | 2 ГБ        | +100%     | +22%    │
│───────────────────|─────────|─────────────|───────────|──────── │
│ **ИТОГО**         |         |             |           | **+23%**│
└─────────────────────────────────────────────────────────────────┘

import numpy as np
import pandas as pd
from skopt import BayesSearchCV
from skopt.space import Integer, Real
from sklearn.ensemble import RandomForestRegressor
import logging
import joblib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SettingsOptimizer:
    
    Оптимизация настроек кластера с помощью байесовской оптимизации
    
    
    def __init__(self):
        self.best_params = None
        self.optimizer = None
        self.model = None
        
        # Пространство параметров для поиска
        self.param_space = {
            'ras_processes': Integer(1, 8),           # процессы RAS
            'rmng_processes': Integer(2, 16),         # процессы RMNG
            'rphost_processes': Integer(4, 32),       # процессы RPHOST
            'shared_memory_gb': Real(1, 16),          # разделяемая память (ГБ)
            'cache_size_mb': Integer(512, 4096),      # размер кэша (МБ)
            'db_connections': Integer(50, 500),       # соединений с БД
            'lock_timeout_ms': Integer(1000, 30000),  # таймаут блокировок (мс)
        }
        
    def load_performance_tests(self):
        
        Загрузка результатов тестов производительности
        
        # TODO: загрузить данные тестов
        # columns: test_id, ras_processes, rmng_processes, rphost_processes,
        # shared_memory, cache_size, avg_response_time, max_users, cpu_usage
        pass
    
    def run_performance_test(self, params):
        
        Запуск теста производительности с заданными параметрами
        (в реальности - вызов скрипта тестирования)
        
        # TODO: запуск теста
        # metrics = {
        #     'avg_response_time': ...,
        #     'max_users': ...,
        #     'cpu_usage': ...,
        #     'memory_usage': ...
        # }
        # return metrics
        pass
    
    def create_surrogate_model(self, X, y):
       
        Создание суррогатной модели для оптимизации
        
        self.model = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        self.model.fit(X, y)
        logger.info(f"Суррогатная модель обучена. R² = {self.model.score(X, y):.3f}")
        
        return self.model
    
    def bayesian_optimization(self, X, y, n_iter=50):
        
        Байесовская оптимизация параметров
        
        # Создание суррогатной модели
        self.create_surrogate_model(X, y)
        
        # Пространство поиска
        search_spaces = {
            'ras_processes': Integer(1, 8),
            'rmng_processes': Integer(2, 16),
            'rphost_processes': Integer(4, 32),
            'shared_memory_gb': Real(1, 16),
            'cache_size_mb': Integer(512, 4096)
        }
        
        # Байесовская оптимизация
        self.optimizer = BayesSearchCV(
            self.model,
            search_spaces,
            n_iter=n_iter,
            cv=3,
            scoring='neg_mean_squared_error',
            random_state=42
        )
        
        # TODO: оптимизация
        # self.optimizer.fit(X, y)
        # self.best_params = self.optimizer.best_params_
        
        return self.best_params
    
    def suggest_settings(self, current_settings):
        
        Формирование рекомендаций по настройкам
        
        if not self.best_params:
            return None
        
        recommendations = []
        total_improvement = 0
        
        for param, optimal_value in self.best_params.items():
            current = current_settings.get(param)
            if current:
                change = ((optimal_value - current) / current) * 100
                
                # Оценка влияния (упрощенно)
                impact = abs(change) * 0.3  # 30% от изменения
                total_improvement += impact
                
                recommendations.append({
                    'parameter': param,
                    'current': current,
                    'optimal': optimal_value,
                    'change': change,
                    'impact': impact
                })
        
        return {
            'recommendations': recommendations,
            'total_improvement': total_improvement
        }
    
    def predict_performance(self, params):
        
        Прогноз производительности для заданных параметров
        
        if not self.model:
            raise ValueError("Модель не обучена")
        
        # TODO: преобразование параметров в признаки
        # X_pred = ...
        # prediction = self.model.predict(X_pred)
        
        # return prediction
        pass
    
    def generate_report(self, current_settings, recommendations):
        
        Генерация отчета с рекомендациями
       
        report = []
        
        for rec in recommendations['recommendations']:
            # Определение статуса
            if abs(rec['change']) > 50:
                status = '🔴 Критично'
            elif abs(rec['change']) > 20:
                status = '🟡 Внимание'
            else:
                status = '🟢 Норма'
            
            report.append({
                'parameter': rec['parameter'],
                'current': rec['current'],
                'optimal': rec['optimal'],
                'change': f"{rec['change']:+.0f}%",
                'impact': f"{rec['impact']:+.0f}%",
                'status': status
            })
        
        return pd.DataFrame(report)


def main():
    
    Точка входа для тестирования
    
    optimizer = SettingsOptimizer()
    
    # TODO: загрузить данные тестов
    # df = optimizer.load_performance_tests()
    
    # TODO: байесовская оптимизация
    # X = df[['ras_processes', 'rmng_processes', 'rphost_processes', ...]]
    # y = df['avg_response_time']
    # best_params = optimizer.bayesian_optimization(X, y)
    
    # TODO: рекомендации
    # current_settings = {
    #     'ras_processes': 2,
    #     'rmng_processes': 4,
    #     'rphost_processes': 8,
    #     'shared_memory_gb': 4,
    #     'cache_size_mb': 1024
    # }
    # recommendations = optimizer.suggest_settings(current_settings)
    
    logger.info("Модуль в разработке. См. docs/future_1C_ML.md для деталей.")


if __name__ == "__main__":
    main()
