#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Фабрика для создания ITSM-клиентов на основе конфигурации
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('itsm.factory')

def create_itsm_client():
    """
    Создает экземпляр ITSM-клиента в соответствии с настройками .env
    
    Returns:
        ITSMClient: экземпляр клиента
        
    Raises:
        ValueError: если тип ITSM не поддерживается или не настроен
    """
    itsm_type = os.getenv('ITSM_TYPE', 'none').lower()
    
    if itsm_type == 'none' or itsm_type == '':
        logger.warning("ITSM_TYPE не задан, интеграция отключена")
        return None
    
    logger.info(f"Создание ITSM-клиента типа: {itsm_type}")
    
    if itsm_type == 'jira':
        from .jira_integration import JiraClient
        return JiraClient()
    
    elif itsm_type == 'youtrack':
        from .youtrack_integration import YouTrackClient
        return YouTrackClient()
    
    elif itsm_type == 'servicenow':
        from .servicenow_integration import ServiceNowClient
        return ServiceNowClient()
    
    elif itsm_type == 'redmine':
        from .redmine_integration import RedmineClient
        return RedmineClient()
    
    elif itsm_type == 'gitlab':
        from .gitlab_integration import GitLabClient
        return GitLabClient()
    
    else:
        raise ValueError(f"Неподдерживаемый тип ITSM: {itsm_type}")

def get_available_clients():
    """Возвращает список доступных типов клиентов"""
    return ['jira', 'youtrack', 'servicenow', 'redmine', 'gitlab']
