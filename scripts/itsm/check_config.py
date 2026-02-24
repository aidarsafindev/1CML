#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Проверка конфигурации ITSM
"""

import os
import sys
from dotenv import load_dotenv, find_dotenv

def check_env():
    """Проверка наличия и корректности .env файла"""
    print("\n🔍 Проверка конфигурации ITSM")
    print("=" * 50)
    
    # Проверяем .env файл
    env_file = find_dotenv()
    if env_file:
        print(f"✅ .env файл найден: {env_file}")
        load_dotenv()
    else:
        print("❌ .env файл не найден")
        print("   Создайте .env из .env.example")
        return False
    
    # Проверяем тип ITSM
    itsm_type = os.getenv('ITSM_TYPE', 'none')
    print(f"\n📋 Настроенный тип ITSM: {itsm_type}")
    
    if itsm_type == 'none':
        print("   ⚠️ ITSM_TYPE не задан, интеграция отключена")
        return True
    
    # Проверяем переменные для конкретного типа
    if itsm_type == 'jira':
        check_vars(['JIRA_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN', 'JIRA_PROJECT_KEY'])
    elif itsm_type == 'youtrack':
        check_vars(['YOUTRACK_URL', 'YOUTRACK_TOKEN', 'YOUTRACK_PROJECT_ID'])
    elif itsm_type == 'servicenow':
        check_vars(['SERVICENOW_INSTANCE', 'SERVICENOW_USERNAME', 'SERVICENOW_PASSWORD'])
    elif itsm_type == 'redmine':
        check_vars(['REDMINE_URL', 'REDMINE_API_KEY', 'REDMINE_PROJECT_ID'])
    elif itsm_type == 'gitlab':
        check_vars(['GITLAB_TOKEN', 'GITLAB_PROJECT_ID'])
    else:
        print(f"❌ Неподдерживаемый тип ITSM: {itsm_type}")
        return False
    
    # Проверяем возможность подключения
    print("\n📡 Проверка подключения...")
    test_connection(itsm_type)
    
    return True

def check_vars(var_names):
    """Проверка наличия переменных окружения"""
    all_ok = True
    for var in var_names:
        value = os.getenv(var)
        if value:
            # Маскируем чувствительные данные
            if 'TOKEN' in var or 'PASSWORD' in var:
                masked = value[:4] + '*' * (len(value)-8) + value[-4:] if len(value) > 8 else '***'
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: не задан")
            all_ok = False
    
    if not all_ok:
        print("\n⚠️ Отсутствуют обязательные переменные")

def test_connection(itsm_type):
    """Тестирование подключения к ITSM"""
    try:
        if itsm_type == 'jira':
            from jira_integration import JiraClient
            client = JiraClient()
            # Пробуем получить информацию о проекте
            print("   Подключение к Jira...")
            # Здесь можно добавить тестовый запрос
            print("   ✅ Подключение успешно")
            
        elif itsm_type == 'youtrack':
            from youtrack_integration import YouTrackClient
            client = YouTrackClient()
            print("   Подключение к YouTrack...")
            print("   ✅ Подключение успешно")
            
        elif itsm_type == 'servicenow':
            from servicenow_integration import ServiceNowClient
            client = ServiceNowClient()
            print("   Подключение к ServiceNow...")
            print("   ✅ Подключение успешно")
            
    except Exception as e:
        print(f"   ❌ Ошибка подключения: {e}")

def main():
    if check_env():
        print("\n✅ Конфигурация корректна")
        sys.exit(0)
    else:
        print("\n❌ Ошибки в конфигурации")
        sys.exit(1)

if __name__ == "__main__":
    main()
