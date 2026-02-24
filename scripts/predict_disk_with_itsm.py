#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Пример интеграции прогноза диска с ITSM
Расширенная версия predict_disk.py с созданием тикетов
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Добавляем путь к ITSM модулю
sys.path.append(os.path.join(os.path.dirname(__file__), 'itsm'))
from factory import create_itsm_client

# Импортируем оригинальный скрипт
from predict_disk import main as original_main, DISK_LIMIT_GB, DISK_LETTER

logger = logging.getLogger('predict_with_itsm')
load_dotenv()

def create_itsm_ticket(warnings, metrics):
    """Создание тикета в ITSM при критическом прогнозе"""
    
    if not warnings:
        return
    
    try:
        client = create_itsm_client()
        if not client:
            logger.warning("ITSM клиент не настроен, пропускаем создание тикета")
            return
        
        # Формируем заголовок
        summary = f"[Превентивно] Прогноз заполнения диска {DISK_LETTER}"
        
        # Рассчитываем срок
        days_to_limit = metrics.get('days_to_limit', 14)
        if days_to_limit <= 7:
            due_days = max(1, days_to_limit - 1)
            priority = "Highest"
        elif days_to_limit <= 14:
            due_days = max(2, days_to_limit - 2)
            priority = "High"
        else:
            due_days = max(3, days_to_limit - 3)
            priority = "Medium"
        
        due_date = (datetime.now() + timedelta(days=due_days)).strftime('%Y-%m-%d')
        
        # Формируем описание
        description = f"""
*Автоматически создано системой прогнозирования 1CML*

**Проблема:** Прогнозируется заполнение диска {DISK_LETTER} в ближайшее время

**Текущие метрики:**
- Текущий объем: {metrics.get('current', 0):.1f} ГБ
- Скорость роста: {metrics.get('growth_rate', 0):.2f} ГБ/день
- Прогноз через 7 дней: {metrics.get('forecast_7d', 0):.1f} ГБ
- Прогноз через 14 дней: {metrics.get('forecast_14d', 0):.1f} ГБ
- Прогноз через 30 дней: {metrics.get('forecast_30d', 0):.1f} ГБ
- Дней до заполнения: {days_to_limit:.0f}

**Критические предупреждения:**
{chr(10).join(['- ' + w for w in warnings])}

**Рекомендация:**
- Расширить диск или очистить архивные данные
- Срок выполнения: до {due_date}

**Ссылки:**
- Дашборд: http://grafana:3000/d/disk-forecast
- Лог прогноза: /var/log/1cml/disk_predict.log

*Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Уверенность модели: {metrics.get('confidence', 90):.1f}%*
"""
        
        logger.info(f"Создание задачи в ITSM...")
        issue_id = client.create_issue(
            summary=summary,
            description=description,
            priority=priority,
            due_date=due_date
        )
        
        if issue_id:
            logger.info(f"✅ Задача создана: {issue_id}")
            
            # Добавляем комментарий
            client.add_comment(
                issue_id,
                f"Прогноз сгенерирован {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"Метрики: {metrics}"
            )
            
            # Отправляем уведомление в Telegram (опционально)
            try:
                from alert_telegram import send_telegram_alert
                send_telegram_alert(
                    f"📋 Создана задача в ITSM: {issue_id}\n"
                    f"Приоритет: {priority}\n"
                    f"Срок: {due_date}\n"
                    f"Дней до заполнения: {days_to_limit}"
                )
            except:
                pass
            
            return issue_id
        else:
            logger.error("❌ Ошибка создания задачи")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания тикета: {e}")
        return None

def main_with_itsm():
    """Запуск прогноза с созданием тикетов"""
    
    # Запускаем оригинальный прогноз
    result = original_main()  # Предполагается, что original_main возвращает метрики
    
    # Создаем тикет при необходимости
    if result and result.get('warnings'):
        create_itsm_ticket(result['warnings'], result['metrics'])

if __name__ == "__main__":
    main_with_itsm()
