# app/handlers/registration.py
from aiogram import Router, F
from aiogram.types import Message
from app.db.database import get_resident_by_name, register_user, get_resident_by_tg_id

router = Router()

@router.message(F.text)
async def process_registration(message: Message):
    # Проверяем, может пользователь уже зарегистрирован
    existing_user = await get_resident_by_tg_id(message.from_user.id)
    if existing_user:
        await message.answer("Вы уже зарегистрированы. Для просмотра команд введите /start.")
        return

    name = message.text.strip()
    resident = await get_resident_by_name(name)

    if resident:
        # Проверяем, не занят ли этот профиль другим telegram_id
        if resident[2] is not None:
            await message.answer("Этот житель уже зарегистрирован в системе. Если это ошибка, обратитесь к администратору.")
        else:
            await register_user(resident_id=resident[0], telegram_id=message.from_user.id)
            await message.answer(
                f"Отлично, {resident[1]}! 🎉\n"
                "Регистрация прошла успешно. Теперь ты будешь получать уведомления о дежурствах.\n"
                "Чтобы увидеть доступные команды, введи /start."
            )
    else:
        await message.answer("Такого имени нет в списке жильцов. Попробуй еще раз. Убедись, что имя написано без ошибок.")