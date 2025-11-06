# app/handlers/admin.py
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command

# !! ВАЖНО: Замени 123456789 на твой реальный Telegram ID
# !! Чтобы узнать свой ID, можно написать боту @userinfobot
ADMIN_IDS = [] # Можно добавить несколько ID: [123456, 789456]

# Импортируем нужные функции
from app.scheduler.tasks import assign_duties
from app.db.database import get_current_week_schedule, is_schedule_empty
from app.utils.error_logging import ERROR_LOGS, add_error_log

router = Router()

# Фильтр для проверки, является ли пользователь администратором
class AdminFilter(F.filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("У вас нет прав на выполнение этой команды.")
            return False
        return True

# Команда 1: /admin_force_assignment (Назначить новую уборку)
@router.message(AdminFilter(), Command("admin_force_assignment"))
async def admin_force_assignment(message: Message, bot: Bot):
    """
    Принудительно запускает процесс назначения дежурств.
    """
    await message.answer("⚠️ Получена команда на принудительное назначение дежурств.\nЗапускаю процесс...")
    try:
        await assign_duties(bot)
        await message.answer("✅ Процесс назначения дежурств завершен. Новые дежурные (если были) уведомлены.")
    except Exception as e:
        error_msg = f"admin_force_assignment: {e}"
        add_error_log(error_msg)
        await message.answer(f"❌ ОШИБКА при назначении дежурств: {e}")

# Команда 2: /admin_check_schedule (Проверить даты/план уборки)
@router.message(AdminFilter(), Command("admin_check_schedule"))
async def admin_check_schedule(message: Message):
    """
    Показывает текущий план уборки (аналог /schedule).
    """
    if await is_schedule_empty():
        await message.answer("База данных расписаний пуста. Дежурств еще не было.")
        return
        
    schedule_data = await get_current_week_schedule()
    
    if not schedule_data:
        await message.answer("🧹 План уборки на эту смену еще не сформирован (хотя в БД что-то есть).")
        return

    # (Код взят из common.py)
    response = "🗓️ **План уборки на текущую смену:**\n\n"
    for duty in schedule_data:
        status_icon = "✅ Выполнено" if duty['is_completed'] else "❌ Не выполнено"
        response += f"**{duty['room_name']}**: {duty['resident_name']} ({status_icon})\n"
    
    await message.answer(response)

# Команда 3: /admin_logs (Проверить ошибки)
@router.message(AdminFilter(), Command("admin_logs"))
async def admin_show_logs(message: Message):
    """
    Показывает последние 20 ошибок из лога в памяти.
    """
    if not ERROR_LOGS:
        await message.answer("✅ Лог ошибок пуст. Все работает штатно.")
        return
        
    response = "🖥️ **Последние 20 ошибок:**\n\n"
    # Показываем в обратном порядке (самые новые вверху)
    for log_entry in reversed(ERROR_LOGS):
        response += f"- {log_entry}\n"
        
    await message.answer(response)

# Команда 4: /admin_help (Список админ-команд)
@router.message(AdminFilter(), Command("admin_help"))
async def admin_help(message: Message):
    """
    Показывает список доступных админ-команд.
    """
    await message.answer(
        "**Админ-панель**\n\n"
        "/admin_force_assignment - Немедленно запускает процесс назначения новых дежурств.\n"
        "/admin_check_schedule - Показывает текущий план уборки (аналог /schedule).\n"
        "/admin_logs - Показывает последние 20 ошибок бота.\n"
        "/admin_help - Показывает это сообщение."
    )