#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Интеграция с Redmine
Документация API: https://www.redmine.org/projects/redmine/wiki/Rest_api
"""

import os
import logging
import requests
from .base import ITSMClient

logger = logging.getLogger('itsm.redmine')

class RedmineClient(ITSMClient):
    """Клиент для работы с Redmine REST API"""
    
    def __init__(self):
        super().__init__()
        
        self.url = os.getenv('REDMINE_URL')
        self.api_key = os.getenv('REDMINE_API_KEY')
        self.project_id = os.getenv('REDMINE_PROJECT_ID')
        
        if not all([self.url, self.api_key, self.project_id]):
            missing = []
            if not self.url: missing.append('REDMINE_URL')
            if not self.api_key: missing.append('REDMINE_API_KEY')
            if not self.project_id: missing.append('REDMINE_PROJECT_ID')
            raise ValueError(f"Отсутствуют обязательные параметры Redmine: {', '.join(missing)}")
        
        self.headers = {
            'X-Redmine-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # Маппинг приоритетов
        self.priority_map = {
            'Highest': '5',
            'High': '4',
            'Medium': '3',
            'Low': '2',
            'Lowest': '1'
        }
        
        logger.info(f"Redmine клиент инициализирован: {self.url}, проект: {self.project_id}")
    
    def create_issue(self, summary, description, priority='Medium',
                    assignee=None, due_date=None, issue_type='Task'):
        """
        Создание задачи в Redmine
        """
        url = f"{self.url}/issues.json"
        
        payload = {
            'issue': {
                'project_id': self.project_id,
                'subject': summary,
                'description': description,
                'priority_id': self.priority_map.get(priority, '3')
            }
        }
        
        if assignee:
            user_id = self._get_user_id(assignee)
            if user_id:
                payload['issue']['assigned_to_id'] = user_id
        
        if due_date:
            payload['issue']['due_date'] = due_date
        
        try:
            logger.info(f"Создание задачи в Redmine: {summary[:50]}...")
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                issue_id = result['issue']['id']
                logger.info(f"✅ Задача создана: #{issue_id}")
                return str(issue_id)
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
        url = f"{self.url}/issues/{issue_id}.json"
        
        payload = {
            'issue': {
                'notes': comment
            }
        }
        
        try:
            response = requests.put(
                url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Комментарий добавлен к #{issue_id}")
                return True
            else:
                logger.error(f"❌ Ошибка добавления комментария: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении комментария: {e}")
            return False
    
    def _get_user_id(self, username):
        """Получение ID пользователя по логину"""
        url = f"{self.url}/users.json"
        params = {'name': username}
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                users = response.json()['users']
                if users:
                    return users[0]['id']
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
