#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Интеграция с GitLab Issues
Документация API: https://docs.gitlab.com/ee/api/issues.html
"""

import os
import logging
import requests
from .base import ITSMClient

logger = logging.getLogger('itsm.gitlab')

class GitLabClient(ITSMClient):
    """Клиент для работы с GitLab Issues API"""
    
    def __init__(self):
        super().__init__()
        
        self.url = os.getenv('GITLAB_URL', 'https://gitlab.com')
        self.token = os.getenv('GITLAB_TOKEN')
        self.project_id = os.getenv('GITLAB_PROJECT_ID')
        
        if not all([self.token, self.project_id]):
            missing = []
            if not self.token: missing.append('GITLAB_TOKEN')
            if not self.project_id: missing.append('GITLAB_PROJECT_ID')
            raise ValueError(f"Отсутствуют обязательные параметры GitLab: {', '.join(missing)}")
        
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        # Маппинг приоритетов через лейблы
        self.priority_labels = {
            'Highest': 'priority::critical',
            'High': 'priority::high',
            'Medium': 'priority::medium',
            'Low': 'priority::low',
            'Lowest': 'priority::lowest'
        }
        
        logger.info(f"GitLab клиент инициализирован: {self.url}, проект: {self.project_id}")
    
    def create_issue(self, summary, description, priority='Medium',
                    assignee=None, due_date=None, issue_type='Task'):
        """
        Создание Issue в GitLab
        """
        url = f"{self.url}/api/v4/projects/{self.project_id}/issues"
        
        payload = {
            'title': summary,
            'description': description,
            'labels': self.priority_labels.get(priority, 'priority::medium')
        }
        
        if assignee:
            user_id = self._get_user_id(assignee)
            if user_id:
                payload['assignee_ids'] = [user_id]
        
        if due_date:
            payload['due_date'] = due_date
        
        try:
            logger.info(f"Создание Issue в GitLab: {summary[:50]}...")
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                issue_iid = result['iid']
                issue_url = result['web_url']
                logger.info(f"✅ Issue создан: !{issue_iid} - {issue_url}")
                return str(issue_iid)
            else:
                logger.error(f"❌ Ошибка создания Issue: {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Исключение при создании Issue: {e}")
            return None
    
    def add_comment(self, issue_iid, comment):
        """
        Добавление комментария к Issue
        """
        url = f"{self.url}/api/v4/projects/{self.project_id}/issues/{issue_iid}/notes"
        
        payload = {
            'body': comment
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Комментарий добавлен к !{issue_iid}")
                return True
            else:
                logger.error(f"❌ Ошибка добавления комментария: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении комментария: {e}")
            return False
    
    def _get_user_id(self, username):
        """Получение ID пользователя по username"""
        url = f"{self.url}/api/v4/users"
        params = {'username': username}
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                users = response.json()
                if users:
                    return users[0]['id']
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
