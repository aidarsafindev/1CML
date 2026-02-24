#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Интеграция с ServiceNow
Документация API: https://developer.servicenow.com/dev.do#!/reference/api/rome/rest/
"""

import os
import logging
import requests
from .base import ITSMClient

logger = logging.getLogger('itsm.servicenow')

class ServiceNowClient(ITSMClient):
    """Клиент для работы с ServiceNow Table API"""
    
    def __init__(self):
        super().__init__()
        
        self.instance = os.getenv('SERVICENOW_INSTANCE')
        self.username = os.getenv('SERVICENOW_USERNAME')
        self.password = os.getenv('SERVICENOW_PASSWORD')
        
        if not all([self.instance, self.username, self.password]):
            missing = []
            if not self.instance: missing.append('SERVICENOW_INSTANCE')
            if not self.username: missing.append('SERVICENOW_USERNAME')
            if not self.password: missing.append('SERVICENOW_PASSWORD')
            raise ValueError(f"Отсутствуют обязательные параметры ServiceNow: {', '.join(missing)}")
        
        self.url = f"https://{self.instance}.service-now.com/api/now/table/incident"
        self.auth = (self.username, self.password)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Маппинг приоритетов
        self.urgency_map = {
            'Highest': 1,
            'High': 1,
            'Medium': 2,
            'Low': 3,
            'Lowest': 3
        }
        
        self.impact_map = {
            'Highest': 1,
            'High': 2,
            'Medium': 2,
            'Low': 3,
            'Lowest': 3
        }
        
        logger.info(f"ServiceNow клиент инициализирован: {self.instance}")
    
    def create_issue(self, summary, description, priority='Medium',
                    assignee=None, due_date=None, issue_type='Incident'):
        """
        Создание инцидента в ServiceNow
        
        Args:
            summary: краткое описание
            description: полное описание
            priority: приоритет
            assignee: кому назначить (sys_id)
            due_date: срок (не поддерживается напрямую)
            
        Returns:
            str: номер инцидента (INC0012345)
        """
        urgency = self.urgency_map.get(priority, 2)
        impact = self.impact_map.get(priority, 2)
        
        payload = {
            'short_description': summary,
            'description': description,
            'urgency': urgency,
            'impact': impact,
            'category': 'Infrastructure',
            'subcategory': 'Disk Space',
            'caller_id': 'system',
            'assignment_group': os.getenv('SERVICENOW_ASSIGNMENT_GROUP')
        }
        
        if assignee:
            payload['assigned_to'] = assignee
        
        try:
            logger.info(f"Создание инцидента в ServiceNow: {summary[:50]}...")
            response = requests.post(
                self.url,
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code in [200, 201]:
                result = response.json()['result']
                incident_number = result['number']
                logger.info(f"✅ Инцидент создан: {incident_number}")
                return incident_number
            else:
                logger.error(f"❌ Ошибка создания инцидента: {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Исключение при создании инцидента: {e}")
            return None
    
    def add_comment(self, issue_number, comment):
        """
        Добавление комментария (work note) к инциденту
        """
        # Получаем sys_id инцидента по номеру
        sys_id = self._get_incident_sys_id(issue_number)
        if not sys_id:
            return False
        
        url = f"https://{self.instance}.service-now.com/api/now/table/incident/{sys_id}"
        
        payload = {
            'work_notes': comment
        }
        
        try:
            response = requests.patch(
                url,
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Комментарий добавлен к {issue_number}")
                return True
            else:
                logger.error(f"❌ Ошибка добавления комментария: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при добавлении комментария: {e}")
            return False
    
    def _get_incident_sys_id(self, incident_number):
        """Получение sys_id инцидента по номеру"""
        url = f"https://{self.instance}.service-now.com/api/now/table/incident"
        params = {
            'sysparm_query': f'number={incident_number}',
            'sysparm_fields': 'sys_id'
        }
        
        try:
            response = requests.get(
                url,
                auth=self.auth,
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()['result']
                if result:
                    return result[0]['sys_id']
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения sys_id: {e}")
            return None
