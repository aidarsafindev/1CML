Классификация ошибок пользователей 1С
Выявление типичных ошибок по ролям и рекомендации по обучению

Идея для будущей реализации
Запуск: раз в неделю

👥 Анализ ошибок пользователей за март 2026

┌─────────────────────────────────────────────────────────────────┐
│ Топ-5 типов ошибок                                              │
├─────────────────────────────────────────────────────────────────┤
│ 1. "Недостаточно прав" (45% случаев)                            │
│    • Чаще всего у роли: "Менеджер" (60%)                        │
│    • Операции: "Удаление документа", "Изменение даты"           │
│    • 💡 Рекомендация: проверить настройки ролей                 │
│                                                                 │
│ 2. "Деление на ноль" (23% случаев)                              │
│    • Чаще всего у роли: "Бухгалтер" (75%)                       │
│    • Операция: "Расчет себестоимости"                           │
│    • 💡 Рекомендация: добавить проверку в код                   │
└─────────────────────────────────────────────────────────────────┘

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
import logging
import joblib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UserErrorClassifier:
   
    Классификация ошибок пользователей
    
    
    def __init__(self):
        self.classifier = None
        self.vectorizer = None
        self.error_types = [
            'permission_error',      # недостаточно прав
            'division_by_zero',      # деление на ноль
            'missing_data',          # отсутствуют данные
            'lock_timeout',          # таймаут блокировки
            'network_error',         # сетевая ошибка
            'conversion_error',      # ошибка конвертации
            'db_error',              # ошибка базы данных
            'interface_error'        # ошибка интерфейса
        ]
        
    def load_errors_from_clickhouse(self, days=30):
        
        Загрузка ошибок из ClickHouse
        
        # TODO: запрос к ClickHouse
        # SELECT 
        #     event_date,
        #     user_name,
        #     user_role,
        #     error_text,
        #     operation_name,
        #     context
        # FROM error_events
        # WHERE event_date >= NOW() - INTERVAL '%s days'
        pass
    
    def prepare_features(self, df):
        
        Подготовка признаков для классификации
       
        # Текст ошибки
        df['error_text_clean'] = df['error_text'].str.lower()
        
        # Контекст операции
        df['operation'] = df['operation_name'].fillna('')
        
        # Объединенный текст для векторизации
        df['text_for_vector'] = df['error_text_clean'] + ' ' + df['operation']
        
        return df
    
    def train_naive_bayes(self, df):
        
        Обучение наивного байесовского классификатора
       
        # Подготовка данных
        df = self.prepare_features(df)
        
        # Разметка типов ошибок (нужна ручная разметка или правила)
        # В реальности нужно иметь размеченные данные
        df['error_type'] = self.label_errors(df)
        
        # Разделение на train/test
        X_train, X_test, y_train, y_test = train_test_split(
            df['text_for_vector'], 
            df['error_type'],
            test_size=0.2,
            random_state=42
        )
        
        # Создание пайплайна
        self.classifier = Pipeline([
            ('vectorizer', TfidfVectorizer(max_features=500, stop_words=['в', 'на', 'с', 'по', 'для'])),
            ('classifier', MultinomialNB())
        ])
        
        # Обучение
        self.classifier.fit(X_train, y_train)
        
        # Оценка
        score = self.classifier.score(X_test, y_test)
        logger.info(f"Модель обучена. Точность: {score:.3f}")
        
        return self.classifier
    
    def train_svm(self, df):
       
        Обучение SVM классификатора
        
        # Подготовка данных
        df = self.prepare_features(df)
        df['error_type'] = self.label_errors(df)
        
        X_train, X_test, y_train, y_test = train_test_split(
            df['text_for_vector'], 
            df['error_type'],
            test_size=0.2,
            random_state=42
        )
        
        # SVM пайплайн
        self.classifier = Pipeline([
            ('vectorizer', TfidfVectorizer(max_features=500)),
            ('classifier', SVC(kernel='linear', probability=True))
        ])
        
        self.classifier.fit(X_train, y_train)
        
        score = self.classifier.score(X_test, y_test)
        logger.info(f"SVM модель обучена. Точность: {score:.3f}")
        
        return self.classifier
    
    def label_errors(self, df):
        
        Разметка типов ошибок (временная заглушка)
        В реальности нужно иметь размеченные данные или правила
        
        labels = []
        
        for text in df['error_text']:
            text_lower = text.lower()
            
            if 'прав' in text_lower or 'доступ' in text_lower:
                labels.append('permission_error')
            elif 'деление' in text_lower and 'ноль' in text_lower:
                labels.append('division_by_zero')
            elif 'блокировк' in text_lower or 'deadlock' in text_lower:
                labels.append('lock_timeout')
            elif 'сет' in text_lower or 'connection' in text_lower:
                labels.append('network_error')
            elif 'конверт' in text_lower or 'convert' in text_lower:
                labels.append('conversion_error')
            elif 'баз' in text_lower or 'db' in text_lower:
                labels.append('db_error')
            else:
                labels.append('interface_error')
        
        return labels
    
    def analyze_by_role(self, df):
        
        Анализ ошибок по ролям пользователей
        
        # Добавляем тип ошибки
        df['error_type'] = self.label_errors(df)
        
        # Группировка по ролям и типам ошибок
        role_errors = df.groupby(['user_role', 'error_type']).size().unstack(fill_value=0)
        
        # Топ ошибок для каждой роли
        role_stats = {}
        for role in role_errors.index:
            top_errors = role_errors.loc[role].nlargest(3)
            role_stats[role] = {
                'total_errors': role_errors.loc[role].sum(),
                'top_errors': top_errors.to_dict()
            }
        
        return role_stats
    
    def find_users_for_training(self, df, threshold=10):
       
        Поиск пользователей, которым нужно обучение
       
        # Добавляем тип ошибки
        df['error_type'] = self.label_errors(df)
        
        # Группировка по пользователям
        user_stats = df.groupby('user_name').agg({
            'error_text': 'count',
            'error_type': lambda x: x.value_counts().to_dict()
        }).rename(columns={'error_text': 'total_errors'})
        
        # Отбор пользователей с большим числом ошибок
        problem_users = user_stats[user_stats['total_errors'] >= threshold].sort_values(
            'total_errors', ascending=False
        )
        
        return problem_users
    
    def generate_recommendations(self, role_stats, problem_users):
        
        Генерация рекомендаций по обучению
        
        recommendations = []
        
        # Рекомендации по ролям
        for role, stats in role_stats.items():
            if stats['total_errors'] > 50:
                main_error = list(stats['top_errors'].keys())[0]
                
                if main_error == 'permission_error':
                    recommendations.append({
                        'role': role,
                        'type': 'training',
                        'message': f"Провести обучение по правам доступа для роли {role}"
                    })
                elif main_error == 'division_by_zero':
                    recommendations.append({
                        'role': role,
                        'type': 'code_fix',
                        'message': f"Добавить проверки в код для операций роли {role}"
                    })
        
        # Рекомендации по конкретным пользователям
        for user in problem_users.head(5).index:
            recommendations.append({
                'user': user,
                'type': 'individual_training',
                'message': f"Индивидуальное обучение для {user} ({problem_users.loc[user, 'total_errors']} ошибок)"
            })
        
        return recommendations


def main():
    
    Точка входа для тестирования
    
    classifier = UserErrorClassifier()
    
    # TODO: загрузить данные
    # df = classifier.load_errors_from_clickhouse()
    
    # TODO: обучить модель
    # classifier.train_svm(df)
    
    # TODO: анализ по ролям
    # role_stats = classifier.analyze_by_role(df)
    
    # TODO: поиск проблемных пользователей
    # problem_users = classifier.find_users_for_training(df)
    
    # TODO: рекомендации
    # recommendations = classifier.generate_recommendations(role_stats, problem_users)
    
    logger.info("Модуль в разработке. См. docs/future_1C_ML.md для деталей.")


if __name__ == "__main__":
    main()
