# Интеграция с ITSM системами

## 📋 Обзор

Модуль ITSM позволяет автоматически создавать задачи в популярных системах управления проектами при срабатывании прогнозов и алертов.

## 🔧 Поддерживаемые системы

| Система | Версия API | Файл | Статус |
|---------|------------|------|--------|
| Jira Cloud | REST v3 | `jira_integration.py` | ✅ Стабильно |
| Jira Server | REST v2 | `jira_integration.py` | ✅ Стабильно |
| YouTrack | Hub REST | `youtrack_integration.py` | ✅ Стабильно |
| ServiceNow | Table API | `servicenow_integration.py` | ✅ Стабильно |
| Redmine | REST | `redmine_integration.py` | ✅ Стабильно |
| GitLab Issues | REST v4 | `gitlab_integration.py` | ✅ Стабильно |

## 🚀 Быстрый старт

### 1. Настройка переменных окружения

```bash
# Скопируйте шаблон
cp .env.example .env

# Отредактируйте .env, выберите ITSM_TYPE и заполните соответствующие параметры
nano .env


Пример для Jira:

ITSM_TYPE=jira
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=IT

2. Проверка конфигурации
bash
# Проверка настроек
python scripts/itsm/check_config.py

# Тестовое создание задачи
python scripts/itsm/test_create.py --type jira --priority High --days 7
3. Запуск вебхук-обработчика
bash
# Через Docker
docker-compose -f docker-compose.itsm.yml up -d

# Или напрямую Python
python scripts/webhook_handler.py
4. Настройка Alertmanager
Добавьте в prometheus/alertmanager.yml:

yaml
receivers:
- name: 'webhook'
  webhook_configs:
  - url: 'http://localhost:5000/webhook'
🔌 Интеграция с прогнозами
С прогнозом диска
python
from scripts.itsm.factory import create_itsm_client

# Создаем клиент
client = create_itsm_client()

# При критическом прогнозе
if days_to_limit < 14:
    issue_id = client.create_issue(
        summary=f"[Превентивно] Заполнение диска через {days_to_limit} дней",
        description="...",
        priority="High",
        due_date="2026-03-10"
    )
С вебхуками от Alertmanager
Вебхук-обработчик (scripts/webhook_handler.py) автоматически:

Принимает алерты от Alertmanager

Создает задачи в выбранной ITSM системе

Добавляет комментарии с деталями

Логирует все действия

📊 Примеры
Jira задача
https://via.placeholder.com/800x400?text=Jira+Issue+Example

YouTrack задача
https://via.placeholder.com/800x400?text=YouTrack+Issue+Example

🔍 Отладка
Просмотр логов
bash
# Логи вебхук-обработчика
tail -f logs/webhook.log

# Логи ITSM модуля
tail -f logs/itsm.log
Тестирование вебхука
bash
# Отправка тестового алерта
curl -X POST http://localhost:5000/test \
  -H "Content-Type: application/json" \
  -d '{"test": true, "message": "Hello ITSM"}'

# Имитация алерта от Alertmanager
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "Test Alert",
        "severity": "warning",
        "instance": "test-server"
      },
      "annotations": {
        "summary": "Тестовое предупреждение",
        "description": "Проверка интеграции с ITSM"
      }
    }]
  }'
⚙️ Расширение
Добавление новой ITSM системы
Создайте файл scripts/itsm/new_system.py

Унаследуйтесь от ITSMClient из base.py

Реализуйте методы create_issue и add_comment

Добавьте в factory.py

Обновите документацию

python
from .base import ITSMClient

class NewSystemClient(ITSMClient):
    def create_issue(self, summary, description, priority='Medium', **kwargs):
        # Ваша реализация
        pass
    
    def add_comment(self, issue_id, comment):
        # Ваша реализация
        pass
📚 Дополнительная информация
Jira API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/

YouTrack API: https://www.jetbrains.com/help/youtrack/devportal/api.html

ServiceNow API: https://developer.servicenow.com/dev.do#!/reference/api/rome/rest/

Redmine API: https://www.redmine.org/projects/redmine/wiki/Rest_api

GitLab API: https://docs.gitlab.com/ee/api/issues.html
