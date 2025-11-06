# app/utils/error_logging.py
import datetime
from collections import deque

# Глобальный логгер ошибок (простой, в памяти)
# deque(maxlen=20) хранит 20 последних записей
ERROR_LOGS = deque(maxlen=20)

def add_error_log(error_message: str):
    """Добавляет ошибку в лог."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"**{now}**: {error_message}"
    ERROR_LOGS.append(log_entry)
    # Также дублируем в консоль для отладки
    print(f"ERROR LOGGED: {log_entry}")