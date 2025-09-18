# app/handlers/common.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
# Добавляем новый импорт
from app.db.database import get_resident_by_tg_id, get_average_ratings, get_current_week_schedule

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_resident_by_tg_id(message.from_user.id)
    if user:
        # Обновляем текст, добавляя новую команду
        await message.answer(
            f"Привет, {user[1]}! 👋\n"
            "Я бот для управления дежурствами по уборке.\n\n"
            "**Доступные команды:**\n"
            "/schedule - посмотреть текущий план уборки\n"
            "/ratings - посмотреть рейтинг качества уборок"
        )
    else:
        await message.answer(
            "Добро пожаловать! 👋\n"
            "Я бот для управления дежурствами. Похоже, ты еще не зарегистрирован.\n"
            "Пожалуйста, напиши свое **имя** (точно как в списке жильцов), чтобы я мог тебя узнать."
        )

# Новая функция для команды /schedule
@router.message(F.text == "/schedule")
async def cmd_schedule(message: Message):
    # Проверяем, зарегистрирован ли пользователь
    user = await get_resident_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Сначала вам нужно зарегистрироваться. Отправьте свое имя.")
        return

    schedule_data = await get_current_week_schedule()

    if not schedule_data:
        await message.answer("🧹 План уборки на эту смену еще не сформирован.")
        return

    response = "🗓️ **План уборки на текущую смену:**\n\n"
    for duty in schedule_data:
        status_icon = "✅ Выполнено" if duty['is_completed'] else "❌ Не выполнено"
        response += f"**{duty['room_name']}**: {duty['resident_name']} ({status_icon})\n"
    
    await message.answer(response)


@router.message(F.text == "/ratings")
async def cmd_ratings(message: Message):
    user = await get_resident_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Сначала вам нужно зарегистрироваться. Отправьте свое имя.")
        return
        
    ratings = await get_average_ratings()
    if not ratings:
        await message.answer("Пока нет ни одной оценки.")
        return
    
    response = "🏆 **Рейтинг качества уборок** 🏆\n\n"
    for r in ratings:
        avg_rating = r['avg_rating'] if r['avg_rating'] is not None else 0
        star_rating = "⭐" * int(round(avg_rating)) + "☆" * (5 - int(round(avg_rating)))
        response += f"**{r['name']}**: {avg_rating:.2f}/5.00 ({star_rating}) - *оценок: {r['total_ratings']}*\n"
        
    await message.answer(response, parse_mode="Markdown")