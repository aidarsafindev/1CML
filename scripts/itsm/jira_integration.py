#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Интеграция с Jira Cloud/Server
Документация API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

import os
import json
import logging
import requests
from datetime import datetime
from .base import ITSMClient

logger = logging.getLogger('itsm.jira')

class JiraClient(ITSMClient):
    """Клиент для работы с Jira REST API v3"""
    
    def __init__(self):
        super().__init__()
        
        # Загрузка конфигурации из переменных окружения
        self.url = os.getenv('JIRA_URL')
        self.username = os.getenv('JIRA_USERNAME')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'IT')
        
        # Проверка обязательных параметров
        if not all([self.url, self.username, self.api_token]):
            missing = []
            if not self.url: missing.append('JIRA_URL')
            if not self.username: missing.append('JIRA_USERNAME')
            if not self.api_token: missing.append('JIRA_API_TOKEN')
            raise ValueError(f"Отсутствуют обязательные параметры Jira: {', '.join(missing)}")
        
        # Настройка аутентификации
        self.auth = (self.username, self.api_token)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Маппинг приоритетов
        self.priority_map = {
            'Highest': '1',
            'High': '2',
            'Medium': '3',
            'Low': '4',
            'Lowest': '5'
        }
        
        logger.info(f"Jira клиент инициализирован: {self.url}, проект: {self.project_key}")
    
    def create_issue(self, summary, description, priority='Medium',
                    assignee=None, due_date=None, issue_type='Task'):
        """
        Создание задачи в Jira
        
        Args:
            summary: заголовок задачи
            description: описание
            priority: приоритет (Highest/High/Medium/Low/Lowest)
            assignee: кому назначить (username)
            due_date: срок (YYYY-MM-DD)
            issue_type: тип задачи (Task/Bug/Story)
            
        Returns:
            str: ключ задачи (например, IT-123)
        """
        url = f"{self.url}/rest/api/3/issue"
        
        # Формирование описания в формате Atlassian Document Format
        description_doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "text": description,
                            "type": "text"
                        }
                    ]
                }
            ]
        }
        
        # Базовые поля
        fields = {
            "project": {"key": self.project_key},
            "summary": summary,
            "description": description_doc,
            "issuetype": {"name": issue_type}
        }
        
        # Приоритет
        if priority in self.priority_map:
            fields["priority"] = {"id": self.priority_map[priority]}
        
        # Назначение
        if assignee:
            fields["assignee"] = {"name": assignee}
        
        # Срок
        if due_date:
            fields["duedate"] = due_date
        
        payload = {"fields": fields}
        
        try:
            logger.info(f"Создание задачи в Jira: {summary[:50]}...")
            response = requests.post(
                url,
                auth=self.auth,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 201:
                result = response.json()
                issue_key = result['key']
                logger.info(f"✅ Задача создана: {issue_key}")
                return issue_key
            else:
                logger.error(f"❌ Ошибка создания задачи: {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Исключение при создании задачи: {e}")
            return None
    
    def add_comment(self, issue_key, comment):
        """
        Добавление комментария к задаче
        
        Args:
            issue_key: ключ задачи (IT-123)
            comment: текст комментария
            
        Returns:
            bool: успех операции
        """
        url = f"{self.url}/rest/api/3/issue/{issue_key}/comment"
        
        comment_doc = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "text": comment,
                            "type": "text"
                        }
                    ]
                }
            ]
        }
        
        payload = {"body": comment_doc}
        
        try:
            response = requests.post(
                url,
                auth=self.auth,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 201:
                logger.info(f"✅ Комментарий добавлен к {issue_key}")
                return True
            else:
                logger.error(f"❌ Ошибка добавления комментария: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении комментария: {e}")
            return False
    
    def add_attachment(self, issue_key, file_path):
        """
        Добавление вложения к задаче
        
        Args:
            issue_key: ключ задачи
            file_path: путь к файлу
            
        Returns:
            bool: успех операции
        """
        url = f"{self.url}/rest/api/3/issue/{issue_key}/attachments"
        
        headers = {
            'Accept': 'application/json',
            'X-Atlassian-Token': 'no-check'
        }
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'image/png')}
                
                response = requests.post(
                    url,
                    auth=self.auth,
                    headers=headers,
                    files=files
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Вложение добавлено к {issue_key}")
                    return True
                else:
                    logger.error(f"❌ Ошибка добавления вложения: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении вложения: {e}")
            return False
    
    def get_issue(self, issue_key):
        """
        Получение информации о задаче
        
        Args:
            issue_key: ключ задачи
            
        Returns:
            dict: данные задачи или None
        """
        url = f"{self.url}/rest/api/3/issue/{issue_key}"
        
        try:
            response = requests.get(
                url,
                auth=self.auth,
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения задачи: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Исключение при получении задачи: {e}")
            return None
    
    def transition_issue(self, issue_key, transition_id):
        """
        Изменение статуса задачи
        
        Args:
            issue_key: ключ задачи
            transition_id: ID перехода
            
        Returns:
            bool: успех операции
        """
        url = f"{self.url}/rest/api/3/issue/{issue_key}/transitions"
        
        payload = {"transition": {"id": transition_id}}
        
        try:
            response = requests.post(
                url,
                auth=self.auth,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 204:
                logger.info(f"✅ Статус задачи {issue_key} изменен")
                return True
            else:
                logger.error(f"Ошибка изменения статуса: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Исключение при изменении статуса: {e}")
            return False
