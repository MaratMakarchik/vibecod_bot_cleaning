# app/handlers/admin.py
import shlex
from datetime import date
from aiogram import Router, Bot, F
from aiogram.types import Message
# ИЗМЕНЕНО: Добавляем 'Filter'
from aiogram.filters import Command, Filter, CommandObject

# !! Убедитесь, что здесь ВАШ ID (как число, без кавычек)
ADMIN_IDS = [1793655579] # Пример: [123456789]

# Импортируем нужные функции
from app.scheduler.tasks import assign_duties
from app.db.database import (
    get_current_week_schedule, is_schedule_empty,
    # <-- ДОБАВЛЯЕМ НОВЫЕ ИМПОРТЫ
    clear_latest_uncompleted_schedule, get_resident_by_name,
    get_room_by_name, get_latest_schedule_date,
    add_schedule_entry, set_resident_cleaning_stats
)
from app.utils.error_logging import ERROR_LOGS, add_error_log
from app.keyboards.inline import get_confirm_keyboard

router = Router()

# Фильтр для проверки, является ли пользователь администратором
# ИЗМЕНЕНО: Базовый класс теперь 'Filter', а не 'F.filter'
class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("У вас нет прав на выполнение этой команды.")
            return False
        return True

# Команда 1: /admin_force_assignment (Назначить новую уборку)
@router.message(AdminFilter(), Command("admin_force_assignment"))
async def admin_force_assignment(message: Message, bot: Bot):
    """
    Принудительно запускает АВТОМАТИЧЕСКИЙ процесс назначения дежурств.
    (Теперь безопасно, не создает дубликатов).
    """
    await message.answer("⚠️ Получена команда на принудительное *автоматическое* назначение дежурств.\nУдаляю старые записи для СЕГОДНЯ и запускаю процесс...")
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

# Команда 4: /admin_clear_schedule (Очистить текущую неделю)
@router.message(AdminFilter(), Command("admin_clear_schedule"))
async def admin_clear_schedule(message: Message):
    """
    Удаляет все НЕЗАВЕРШЕННЫЕ дежурства для текущей (последней) смены.
    Используй эту команду перед ручным назначением.
    """
    await message.answer("Получена команда на очистку *незавершенных* дежурств для *текущей* смены...")
    try:
        deleted_count = await clear_latest_uncompleted_schedule()
        await message.answer(f"✅ Готово. Удалено записей: {deleted_count}.")
    except Exception as e:
        error_msg = f"admin_clear_schedule: {e}"
        add_error_log(error_msg)
        await message.answer(f"❌ ОШИБКА при очистке расписания: {e}")



# Команда 6: /admin_help (Обновленный)
@router.message(AdminFilter(), Command("admin_help"))
async def admin_help(message: Message):
    """
    Показывает список доступных админ-команд.
    """
    help_text = (
        "<b>🛠 Админ-панель управления уборками</b>\n\n"
        
        "<b>🤖 Автоматическое назначение:</b>\n"
        "• /admin_force_assignment - <i>Полностью перезапускает автоматическое распределение дежурств</i>\n"
        "  (удаляет старые записи за сегодня и создает новые)\n\n"
        
        "<b>📊 Просмотр информации:</b>\n"
        "• /admin_check_schedule - <i>Текущий план уборки</i> (аналог /schedule)\n"
        "• /admin_logs - <i>Последние 20 ошибок бота</i>\n\n"
        
    )
    
    await message.answer(help_text, parse_mode="HTML")