#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовое создание задачи в ITSM
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description='Тестовое создание задачи в ITSM')
    parser.add_argument('--type', default='jira', 
                       choices=['jira', 'youtrack', 'servicenow', 'redmine', 'gitlab'],
                       help='Тип ITSM системы')
    parser.add_argument('--summary', default='[ТЕСТ] Прогноз заполнения диска',
                       help='Заголовок задачи')
    parser.add_argument('--priority', default='High',
                       choices=['Highest', 'High', 'Medium', 'Low', 'Lowest'],
                       help='Приоритет')
    parser.add_argument('--days', type=int, default=7,
                       help='Дней до заполнения')
    args = parser.parse_args()
    
    # Устанавливаем тип ITSM для фабрики
    os.environ['ITSM_TYPE'] = args.type
    
    try:
        from factory import create_itsm_client
        
        client = create_itsm_client()
        if not client:
            print(f"❌ Не удалось создать клиент для {args.type}")
            sys.exit(1)
        
        # Формируем тестовые данные
        due_date = (datetime.now() + timedelta(days=args.days)).strftime('%Y-%m-%d')
        
        summary = f"{args.summary} ({args.type})"
        description = f"""
*Тестовое обращение от {datetime.now().strftime('%Y-%m-%d %H:%M')}*

**Проблема:** Прогнозируется заполнение диска через {args.days} дней

**Метрики:**
- Текущий объем: 156.3 ГБ
- Скорость роста: 2.8 ГБ/день
- Прогноз через 7 дней: 175.9 ГБ
- Прогноз через 14 дней: 195.1 ГБ

**Рекомендация:** Расширить диск до 10.03.2026

*Создано системой тестирования 1CML*
"""
        
        print(f"📋 Создание задачи в {args.type}...")
        print(f"   Заголовок: {summary}")
        print(f"   Приоритет: {args.priority}")
        print(f"   Срок: {due_date}")
        
        issue_id = client.create_issue(
            summary=summary,
            description=description,
            priority=args.priority,
            due_date=due_date
        )
        
        if issue_id:
            print(f"✅ Задача успешно создана!")
            print(f"   ID: {issue_id}")
            
            # Добавляем тестовый комментарий
            client.add_comment(
                issue_id,
                f"Тестовый комментарий от {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            print(f"   ✅ Комментарий добавлен")
        else:
            print(f"❌ Ошибка создания задачи")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
