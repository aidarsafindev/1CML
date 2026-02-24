#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Базовый класс для всех ITSM-клиентов
"""

from abc import ABC, abstractmethod
import logging
from datetime import datetime

logger = logging.getLogger('itsm.base')

class ITSMClient(ABC):
    """Базовый абстрактный класс для интеграции с ITSM системами"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        logger.info(f"Инициализация клиента {self.name}")
    
    @abstractmethod
    def create_issue(self, summary, description, priority='Medium', 
                     assignee=None, due_date=None, issue_type='Task'):
        """
        Создание задачи в ITSM системе
        
        Args:
            summary: заголовок задачи
            description: подробное описание
            priority: приоритет (Highest/High/Medium/Low/Lowest)
            assignee: кому назначить
            due_date: срок выполнения (YYYY-MM-DD)
            issue_type: тип задачи
            
        Returns:
            str: идентификатор созданной задачи
        """
        pass
    
    @abstractmethod
    def add_comment(self, issue_id, comment):
        """
        Добавление комментария к задаче
        
        Args:
            issue_id: идентификатор задачи
            comment: текст комментария
            
        Returns:
            bool: успех операции
        """
        pass
    
    def map_priority(self, severity):
        """
        Маппинг severity из мониторинга в приоритет ITSM
        
        Args:
            severity: critical/warning/info
            
        Returns:
            str: приоритет в формате ITSM
        """
        mapping = {
            'critical': 'Highest',
            'warning': 'High',
            'info': 'Medium'
        }
        return mapping.get(severity, 'Medium')
    
    def calculate_due_date(self, days_to_limit):
        """
        Расчет срока выполнения на основе прогноза
        
        Args:
            days_to_limit: дней до критического порога
            
        Returns:
            str: дата в формате YYYY-MM-DD
        """
        if days_to_limit <= 7:
            due_days = max(1, days_to_limit - 1)
        elif days_to_limit <= 14:
            due_days = max(2, days_to_limit - 2)
        else:
            due_days = max(3, days_to_limit - 3)
        
        due_date = (datetime.now() + timedelta(days=due_days)).strftime('%Y-%m-%d')
        return due_date
    
    def format_description(self, title, metrics, warnings, links=None):
        """
        Форматирование описания задачи
        
        Args:
            title: заголовок
            metrics: словарь с метриками
            warnings: список предупреждений
            links: словарь со ссылками
            
        Returns:
            str: отформатированное описание
        """
        desc = f"""
*Автоматически создано системой прогнозирования 1CML*

**{title}**

**Текущие метрики:**
"""
        for key, value in metrics.items():
            desc += f"- {key}: {value}\n"
        
        if warnings:
            desc += "\n**Предупреждения:**\n"
            for w in warnings:
                desc += f"- ⚠️ {w}\n"
        
        if links:
            desc += "\n**Ссылки:**\n"
            for name, url in links.items():
                desc += f"- {name}: {url}\n"
        
        desc += f"\n*Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        
        return desc
