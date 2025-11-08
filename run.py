# run.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties  # Добавляем импорт
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import BOT_TOKEN, DUTY_CYCLE_WEEKS
# Импортируем новую функцию
from app.db.database import initialize_db, is_schedule_empty
from app.handlers import common, registration, callbacks, admin
# Импортируем assign_duties для вызова при старте
from app.scheduler.tasks import assign_duties, send_reminders, send_overdue_reminders

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализация базы данных
    await initialize_db()

    # Инициализация бота и диспетчера
    # Устанавливаем parse_mode через DefaultBotProperties
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown")  # Новый способ
    )
    dp = Dispatcher()

    # --- Первичное создание расписания при запуске ---
    if await is_schedule_empty():
        logging.info("База данных расписаний пуста. Создаю первоначальный план уборки...")
        try:
            await assign_duties(bot)
            logging.info("Первоначальный план уборки успешно создан.")
        except Exception as e:
            logging.error(f"Не удалось создать первоначальный план уборки: {e}")
    # ---------------------------------------------------

    # Подключение роутеров

    dp.include_router(common.router)
    dp.include_router(callbacks.router)
 
    dp.include_router(admin.router)
    dp.include_router(registration.router)

    # Настройка и запуск планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    scheduler.add_job(assign_duties, 'cron', day_of_week='mon', hour=10, minute=0, week=f'*/{DUTY_CYCLE_WEEKS}', args=(bot,))
    scheduler.add_job(send_reminders, 'cron', day_of_week='mon,wed,sun', hour=12, minute=0, args=(bot,))
    scheduler.add_job(send_overdue_reminders, 'cron', hour='9,15,21', minute=0, args=(bot,))

    scheduler.start()

    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")