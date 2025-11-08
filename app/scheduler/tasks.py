# app/scheduler/tasks.py
import random
from datetime import date
from aiogram import Bot
from app.db.database import (
    get_cleaning_candidates, get_all_rooms, get_all_resident_ids,
    add_schedule_entry, update_resident_cleaning_stats,
    get_uncompleted_duties_for_today, get_overdue_duties,
    delete_schedule_by_date
)
from app.keyboards.inline import get_confirm_keyboard
from app.config import OVERDUE_MESSAGES
from app.utils.error_logging import add_error_log

async def assign_duties(bot: Bot):
    """Назначает дежурных на следующую смену."""
    print("Запускаю процесс назначения дежурных...")
    week_start_date = date.today()
    try:
        await delete_schedule_by_date(week_start_date)
        print(f"Очищены все предыдущие записи для {week_start_date}.")
    except Exception as e:
        error_msg = f"Не удалось очистить расписание для {week_start_date}: {e}"
        print(error_msg)
        add_error_log(error_msg)
        return # Останавливаемся, если не смогли очистить

    candidates = await get_cleaning_candidates() # Теперь это ВСЕ жители, отсортированные
    rooms = await get_all_rooms()

    if len(candidates) < len(rooms):
        # Эта ошибка теперь сработает, только если жителей МЕНЬШЕ, чем комнат
        print(f"Недостаточно кандидатов (жителей: {len(candidates)}) для комнат: {len(rooms)})")
        add_error_log("assign_duties: Not enough residents to fill all rooms.")
        return

    # --- Логика выбора дежурных ---
    
    # ИЗМЕНЕНО: Больше не используем random.sample.
    # Просто берем первых N жителей из отсортированного списка.
    chosen_residents = candidates[:len(rooms)]
    
    shuffled_rooms = list(rooms)
    random.shuffle(shuffled_rooms)
    
    assignments = []
    temp_assignments = {} # {resident_id: room_id}

    # Первичное распределение
    for i, resident in enumerate(chosen_residents):
        temp_assignments[resident['id']] = shuffled_rooms[i]['id']

    # Проверка и исправление конфликтов (уборка той же комнаты подряд)
    for i, resident in enumerate(chosen_residents):
        res_id = resident['id']
        room_id = temp_assignments[res_id]
        if resident['last_cleaned_room_id'] == room_id:
            # Найти другого дежурного для обмена
            swap_candidate_idx = (i + 1) % len(chosen_residents)
            swap_res_id = chosen_residents[swap_candidate_idx]['id']
            
            # Обмен комнатами
            temp_assignments[res_id], temp_assignments[swap_res_id] = temp_assignments[swap_res_id], temp_assignments[res_id]
    
    # Финальный список пар (объект жителя, объект комнаты)
    resident_map = {res['id']: res for res in chosen_residents}
    room_map = {room['id']: room for room in rooms}
    assignments_with_data = [(resident_map[res_id], room_map[room_id]) for res_id, room_id in temp_assignments.items()]
    
    # --- Сохранение в БД и отправка уведомлений ---
    
    notifications_to_send = []

    # 1. Сначала сохраняем все дежурства в БД
    for resident, room in assignments_with_data:
        schedule_id = await add_schedule_entry(resident['id'], room['id'], week_start_date) 
        if resident['telegram_id']:
            notifications_to_send.append({
                'telegram_id': resident['telegram_id'],
                'resident_name': resident['name'],
                'room_name': room['name'],
                'schedule_id': schedule_id
            })

    # 2. Затем обновляем статистику всех жителей
    all_resident_ids = await get_all_resident_ids()
    assigned_id_pairs = [(res['id'], room['id']) for res, room in assignments_with_data]
    await update_resident_cleaning_stats(assigned_id_pairs, all_resident_ids)
    
    # 3. Теперь безопасно отправляем уведомления
    for notification in notifications_to_send:
        try:
            message = (f"🧹 Новое дежурство!\n\n"
                       f"На этой неделе твоя очередь убирать: **{notification['room_name']}**.\n\n"
                       "Когда закончишь, нажми на кнопку ниже.")
            await bot.send_message(
                chat_id=notification['telegram_id'],
                text=message,
                reply_markup=get_confirm_keyboard(notification['schedule_id'])
            )
        except Exception as e:
            # ИЗМЕНЕНО: Логгируем ошибку
            error_msg = f"Не удалось отправить уведомление о назначении жителю {notification['resident_name']}: {e}"
            print(error_msg)
            add_error_log(error_msg)
    
    print(f"Дежурства успешно назначены.")


async def send_reminders(bot: Bot):
   
    print("Sending reminders...")
    duties = await get_uncompleted_duties_for_today()
    for duty in duties:
        if duty['telegram_id']:
            try:
                message = (f"Не забудь, что на этой неделе твоя очередь убирать: **{duty['room_name']}**.\n"
                           "Когда закончишь, нажми на кнопку ниже.")
                await bot.send_message(
                    chat_id=duty['telegram_id'],
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=get_confirm_keyboard(duty['id'])
                )
            except Exception as e:
                error_msg = f"Failed to send reminder to {duty['resident_name']}: {e}"
                print(error_msg)
                add_error_log(error_msg)
       



async def send_overdue_reminders(bot: Bot):
    # ... (эта функция без изменений)
    print("Sending overdue reminders...")
    duties = await get_overdue_duties()
    for duty in duties:
        if duty['telegram_id']:
            try:
                message = random.choice(OVERDUE_MESSAGES).format(room_name=duty['room_name'])
                await bot.send_message(
                    chat_id=duty['telegram_id'],
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=get_confirm_keyboard(duty['id'])
                )
            except Exception as e:
                error_msg = f"Failed to send overdue reminder to {duty['resident_name']}: {e}"
                print(error_msg)
                add_error_log(error_msg)