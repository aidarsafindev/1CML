#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Отправка алертов в Telegram
Поддерживает: текст, форматирование, кнопки
"""

import requests
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
import argparse
import json
from typing import Optional, List, Dict

# Загрузка переменных окружения
load_dotenv(Path(__file__).parent / '../.env')

logger = logging.getLogger('telegram_alert')

class TelegramAlert:
    """Класс для отправки уведомлений в Telegram"""
    
    def __init__(self, token: str = None, chat_id: str = None):
        """
        Инициализация
        
        Args:
            token: токен бота
            chat_id: ID чата/группы
        """
        self.token = token or os.getenv('TELEGRAM_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_TOKEN и TELEGRAM_CHAT_ID должны быть заданы")
        
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, text: str, parse_mode: str = 'Markdown',
                    disable_web_page_preview: bool = True,
                    reply_markup: Optional[Dict] = None) -> bool:
        """
        Отправка текстового сообщения
        
        Args:
            text: текст сообщения
            parse_mode: режим форматирования (Markdown/HTML)
            disable_web_page_preview: отключить предпросмотр ссылок
            reply_markup: клавиатура/кнопки
        
        Returns:
            bool: успешно ли отправлено
        """
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': disable_web_page_preview
            }
            
            if reply_markup:
                payload['reply_markup'] = json.dumps(reply_markup)
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                logger.info(f"Сообщение отправлено в чат {self.chat_id}")
                return True
            else:
                logger.error(f"Ошибка Telegram API: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
            return False
    
    def send_alert(self, title: str, description: str, severity: str = 'warning',
                  details: Optional[Dict] = None, buttons: Optional[List] = None):
        """
        Отправка форматированного алерта
        
        Args:
            title: заголовок
            description: описание
            severity: важность (info/warning/critical)
            details: дополнительные детали
            buttons: кнопки
        """
        # Эмодзи в зависимости от важности
        emoji = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'critical': '🚨'
        }.get(severity, '📢')
        
        # Формируем сообщение
        message = f"{emoji} **{title}**\n\n"
        message += f"{description}\n\n"
        
        if details:
            message += "**Детали:**\n"
            for key, value in details.items():
                message += f"• {key}: `{value}`\n"
            message += "\n"
        
        message += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Кнопки
        reply_markup = None
        if buttons:
            keyboard = []
            for button in buttons:
                if isinstance(button, dict):
                    keyboard.append([{
                        'text': button.get('text', ''),
                        'url': button.get('url', ''),
                        'callback_data': button.get('callback_data')
                    }])
            
            if keyboard:
                reply_markup = {'inline_keyboard': keyboard}
        
        return self.send_message(message, reply_markup=reply_markup)

def send_telegram_alert(message: str, severity: str = 'warning'):
    """
    Упрощенная функция для отправки алерта (для обратной совместимости)
    """
    try:
        alert = TelegramAlert()
        return alert.send_alert(
            title="Мониторинг 1С",
            description=message,
            severity=severity
        )
    except Exception as e:
        logger.error(f"Ошибка отправки алерта: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Отправка алерта в Telegram')
    parser.add_argument('--title', default='Мониторинг 1С', help='Заголовок')
    parser.add_argument('--message', required=True, help='Текст сообщения')
    parser.add_argument('--severity', default='warning',
                       choices=['info', 'warning', 'critical'], help='Важность')
    parser.add_argument('--details', help='JSON с деталями')
    
    args = parser.parse_args()
    
    details = None
    if args.details:
        try:
            details = json.loads(args.details)
        except:
            logger.error("Неверный формат JSON для details")
    
    alert = TelegramAlert()
    success = alert.send_alert(
        title=args.title,
        description=args.message,
        severity=args.severity,
        details=details
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    from datetime import datetime
    import sys
    main()
