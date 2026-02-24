#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Интеграция с YouTrack (JetBrains)
Документация API: https://www.jetbrains.com/help/youtrack/devportal/api.html
"""

import os
import json
import logging
import requests
from .base import ITSMClient

logger = logging.getLogger('itsm.youtrack')

class YouTrackClient(ITSMClient):
    """Клиент для работы с YouTrack API"""
    
    def __init__(self):
        super().__init__()
        
        self.url = os.getenv('YOUTRACK_URL')
        self.token = os.getenv('YOUTRACK_TOKEN')
        self.project_id = os.getenv('YOUTRACK_PROJECT_ID')
        
        if not all([self.url, self.token, self.project_id]):
            missing = []
            if not self.url: missing.append('YOUTRACK_URL')
            if not self.token: missing.append('YOUTRACK_TOKEN')
            if not self.project_id: missing.append('YOUTRACK_PROJECT_ID')
            raise ValueError(f"Отсутствуют обязательные параметры YouTrack: {', '.join(missing)}")
        
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Маппинг приоритетов
        self.priority_map = {
            'Highest': 'Critical',
            'High': 'Major',
            'Medium': 'Normal',
            'Low': 'Minor',
            'Lowest': 'Trivial'
        }
        
        logger.info(f"YouTrack клиент инициализирован: {self.url}, проект: {self.project_id}")
    
    def create_issue(self, summary, description, priority='Medium',
                    assignee=None, due_date=None, issue_type='Task'):
        """
        Создание задачи в YouTrack
        """
        url = f"{self.url}/api/issues"
        
        # Получаем ID приоритета
        priority_name = self.priority_map.get(priority, 'Normal')
        priority_id = self._get_priority_id(priority_name)
        
        # Формируем поля
        fields = {
            'project': {'id': self.project_id},
            'summary': summary,
            'description': description,
            'priority': {'id': priority_id} if priority_id else None
        }
        
        if assignee:
            user_id = self._get_user_id(assignee)
            if user_id:
                fields['assignee'] = {'id': user_id}
        
        if due_date:
            fields['dueDate'] = due_date
        
        # Удаляем None значения
        fields = {k: v for k, v in fields.items() if v is not None}
        
        # YouTrack API требует особый формат
        payload = {
            'fields': json.dumps(fields)
        }
        
        try:
            logger.info(f"Создание задачи в YouTrack: {summary[:50]}...")
            response = requests.post(
                url,
                headers=self.headers,
                data=payload
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                issue_id = result.get('idReadable', result.get('id'))
                logger.info(f"✅ Задача создана: {issue_id}")
                return issue_id
            else:
                logger.error(f"❌ Ошибка создания задачи: {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Исключение при создании задачи: {e}")
            return None
    
    def add_comment(self, issue_id, comment):
        """
        Добавление комментария к задаче
        """
        url = f"{self.url}/api/issues/{issue_id}/comments"
        
        payload = {
            'text': comment
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Комментарий добавлен к {issue_id}")
                return True
            else:
                logger.error(f"❌ Ошибка добавления комментария: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении комментария: {e}")
            return False
    
    def _get_priority_id(self, priority_name):
        """Получение ID приоритета по имени"""
        url = f"{self.url}/api/admin/customFieldSettings/bundles/priority"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                priorities = response.json()
                for p in priorities:
                    if p.get('name') == priority_name:
                        return p.get('id')
            return None
        except Exception as e:
            logger.error(f"Ошибка получения приоритетов: {e}")
            return None
    
    def _get_user_id(self, username):
        """Получение ID пользователя по логину"""
        url = f"{self.url}/api/users"
        params = {'query': username}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                users = response.json()
                if users:
                    return users[0].get('id')
            return None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
