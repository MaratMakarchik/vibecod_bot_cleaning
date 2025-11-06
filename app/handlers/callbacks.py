# app/handlers/callbacks.py
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from app.db.database import (
    complete_duty, get_duty_details_for_rating, 
    get_all_residents_for_rating, save_rating
)
from app.keyboards.inline import get_rating_keyboard
from app.utils.error_logging import add_error_log

router = Router()

@router.callback_query(F.data.startswith("confirm_"))
async def process_confirm_callback(callback: CallbackQuery, bot: Bot):
    schedule_id = int(callback.data.split("_")[1])
    
    await complete_duty(schedule_id)
    
    await callback.message.edit_text("✅ Отлично, спасибо! Твоя работа отмечена.")
    await callback.answer("Уборка подтверждена!")

    # Запускаем процесс оценки
    duty_details = await get_duty_details_for_rating(schedule_id)
    all_residents = await get_all_residents_for_rating()

    rating_message = f"Оцените, пожалуйста, качество уборки в комнате: **{duty_details['room_name']}**."
    rating_keyboard = get_rating_keyboard(schedule_id)

    for res in all_residents:
        # Не отправляем сообщение тому, кто убирался
        if res['telegram_id'] != duty_details['cleaner_tg_id']:
            try:
                await bot.send_message(
                    chat_id=res['telegram_id'],
                    text=rating_message,
                    parse_mode="Markdown",
                    reply_markup=rating_keyboard
                )
            except Exception as e:
                error_msg = f"Failed to send rating request to {res['telegram_id']}: {e}"
                print(error_msg)
                add_error_log(error_msg)

@router.callback_query(F.data.startswith("rate_"))
async def process_rating_callback(callback: CallbackQuery):
    try:
        _, schedule_id_str, rating_str = callback.data.split("_")
        schedule_id = int(schedule_id_str)
        rating = int(rating_str)
        rater_id = callback.from_user.id

        # Тут можно добавить проверку, не голосовал ли пользователь уже
        await save_rating(schedule_id, rater_id, rating)
        
        await callback.message.edit_text(f"Спасибо! Ваша оценка ({rating} ⭐) принята.")
        await callback.answer("Оценка сохранена.")
    except Exception as e:
        error_msg = f"Error processing rating: {e}"
        print(error_msg)
        add_error_log(error_msg)
        await callback.answer("Произошла ошибка или вы уже голосовали.")