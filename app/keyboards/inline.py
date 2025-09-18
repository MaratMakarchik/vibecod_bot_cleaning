# app/keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_confirm_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения уборки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я убрался!", callback_data=f"confirm_{schedule_id}")]
    ])

def get_rating_keyboard(schedule_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для оценки уборки."""
    buttons = [
        [InlineKeyboardButton(text=str(i), callback_data=f"rate_{schedule_id}_{i}") for i in range(1, 6)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)