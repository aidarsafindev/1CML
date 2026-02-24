#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Вебхук-обработчик для Prometheus Alertmanager
Создает задачи в ITSM при получении алертов
"""

from flask import Flask, request, jsonify
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/webhook.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('webhook')

load_dotenv()

# Добавляем путь к ITSM модулю
sys.path.append(os.path.join(os.path.dirname(__file__), 'itsm'))
from factory import create_itsm_client

app = Flask(__name__)

# Создаем ITSM клиент при старте
try:
    itsm_client = create_itsm_client()
    if itsm_client:
        logger.info(f"ITSM клиент инициализирован: {itsm_client.name}")
    else:
        logger.warning("ITSM клиент не создан (ITSM_TYPE=none)")
except Exception as e:
    logger.error(f"Ошибка инициализации ITSM клиента: {e}")
    itsm_client = None

def map_severity_to_priority(severity):
    """Маппинг severity в приоритет ITSM"""
    mapping = {
        'critical': 'Highest',
        'warning': 'High',
        'info': 'Medium'
    }
    return mapping.get(severity, 'Medium')

def extract_metrics(alert):
    """Извлечение метрик из алерта"""
    metrics = {
        'instance': alert.get('labels', {}).get('instance', 'unknown'),
        'job': alert.get('labels', {}).get('job', 'unknown'),
        'severity': alert.get('labels', {}).get('severity', 'warning'),
        'value': alert.get('annotations', {}).get('value', 'N/A')
    }
    return metrics

def format_description(alert):
    """Форматирование описания для ITSM"""
    labels = alert.get('labels', {})
    annotations = alert.get('annotations', {})
    
    desc = f"""
*Автоматически создано системой мониторинга 1CML*

**Алерт:** {labels.get('alertname', 'Unknown')}
**Статус:** {alert.get('status', 'firing')}
**Важность:** {labels.get('severity', 'warning')}
**Источник:** {labels.get('instance', 'unknown')}
**Время:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Описание:**
{annotations.get('description', '')}

**Метрики:**
"""
    for k, v in labels.items():
        if k not in ['alertname', 'severity', 'instance', 'job']:
            desc += f"- {k}: {v}\n"
    
    if annotations.get('summary'):
        desc += f"\n**Сводка:** {annotations.get('summary')}\n"
    
    if annotations.get('runbook_url'):
        desc += f"\n**Runbook:** {annotations.get('runbook_url')}\n"
    
    desc += f"\n*Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    return desc

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Обработка вебхука от Alertmanager"""
    
    if not itsm_client:
        logger.warning("ITSM клиент не настроен, пропускаем")
        return jsonify({"status": "skipped", "reason": "no ITSM client"}), 200
    
    try:
        data = request.json
        logger.info(f"Получен вебхук с {len(data.get('alerts', []))} алертами")
        
        for alert in data.get('alerts', []):
            status = alert.get('status')
            
            if status == 'firing':
                # Создаем задачу для активного алерта
                labels = alert.get('labels', {})
                annotations = alert.get('annotations', {})
                
                summary = annotations.get('summary', labels.get('alertname', 'Unknown Alert'))
                severity = labels.get('severity', 'warning')
                priority = map_severity_to_priority(severity)
                
                description = format_description(alert)
                
                logger.info(f"Создание задачи: {summary[:50]}...")
                
                issue_id = itsm_client.create_issue(
                    summary=f"[{severity.upper()}] {summary}",
                    description=description,
                    priority=priority
                )
                
                if issue_id:
                    logger.info(f"✅ Задача создана: {issue_id}")
                    
                    # Добавляем комментарий с деталями
                    itsm_client.add_comment(
                        issue_id,
                        f"Алерт получен в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Детали: {labels.get('instance', 'unknown')}"
                    )
                else:
                    logger.error(f"❌ Ошибка создания задачи")
                    
            elif status == 'resolved':
                logger.info(f"Алерт resolved: {alert.get('labels', {}).get('alertname')}")
                # Здесь можно закрыть задачу, если нужно
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервиса"""
    status = {
        "status": "healthy",
        "itsm_configured": itsm_client is not None,
        "itsm_type": os.getenv('ITSM_TYPE', 'none'),
        "timestamp": datetime.now().isoformat()
    }
    return jsonify(status), 200

@app.route('/test', methods=['POST'])
def test():
    """Тестовый эндпоинт для отладки"""
    data = request.json
    logger.info(f"Тестовый запрос: {data}")
    
    if itsm_client:
        # Создаем тестовую задачу
        issue_id = itsm_client.create_issue(
            summary="[ТЕСТ] Проверка интеграции",
            description="Тестовое сообщение от вебхук-обработчика",
            priority="Medium"
        )
        return jsonify({"status": "test_ok", "issue_id": issue_id}), 200
    else:
        return jsonify({"status": "no_itsm_client"}), 200

if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Запуск вебхук-обработчика на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
