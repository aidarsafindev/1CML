import numpy as np
from sklearn.linear_model import LinearRegression
import datetime
import requests  # Чтобы слать алерт в Telegram/ITSM

# Это наши исторические данные: дни и размер диска (ГБ)
days = np.array([1, 2, 3, 4, 5]).reshape(-1, 1)
disk_size = np.array([100, 105, 111, 118, 126])

# Учим модель (обычная линейная регрессия!)
model = LinearRegression()
model.fit(days, disk_size)

# Прогноз на 10 дней вперед
future_day = 10
predicted_size = model.predict([[future_day]])

# Проверяем порог
DISK_LIMIT = 200
if predicted_size > DISK_LIMIT:
    message = f"ТРЕВОГА! Диск превысит {DISK_LIMIT}ГБ через {future_day - days[-1][0]} дней. Прогноз: {predicted_size[0]:.0f}ГБ."
    print(message)
    # Шлем в Telegram (бот должен быть настроен)
    # requests.get(f"https://api.telegram.org/.../sendMessage?chat_id=...&text={message}")
else:
    print(f"Пока все спокойно! Прогноз на день {future_day}: {predicted_size[0]:.0f}ГБ")
