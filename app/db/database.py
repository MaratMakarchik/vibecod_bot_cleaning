# app/db/database.py
import aiosqlite
from datetime import date
from app.config import DB_NAME, RESIDENTS, ROOMS

async def initialize_db():
    """Инициализирует базу данных, создает таблицы и заполняет их."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS residents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                telegram_id INTEGER UNIQUE,
                consecutive_cleanings INTEGER DEFAULT 0,
                last_cleaned_room_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id INTEGER,
                room_id INTEGER,
                week_start_date DATE NOT NULL,
                is_completed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (resident_id) REFERENCES residents (id),
                FOREIGN KEY (room_id) REFERENCES rooms (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER,
                rater_telegram_id INTEGER,
                rating_value INTEGER,
                FOREIGN KEY (schedule_id) REFERENCES schedule (id)
            )
        ''')

        # Заполняем таблицы жителей и комнат, если они пусты
        await db.executemany("INSERT OR IGNORE INTO residents (name) VALUES (?)", [(name,) for name in RESIDENTS])
        await db.executemany("INSERT OR IGNORE INTO rooms (name) VALUES (?)", [(name,) for name in ROOMS])
        await db.commit()

# --- Функции для регистрации ---
async def get_resident_by_name(name):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM residents WHERE name = ? COLLATE NOCASE", (name,))
        return await cursor.fetchone()
async def get_room_by_name(name):
    """Находит комнату по имени (без учета регистра)."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM rooms WHERE name = ? COLLATE NOCASE", (name,))
        return await cursor.fetchone()

async def get_latest_schedule_date():
    """Возвращает самую последнюю дату начала смены (week_start_date) из расписания."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT MAX(week_start_date) FROM schedule")
        result = await cursor.fetchone()
        if result and result[0]:
            # aiosqlite возвращает дату как строку 'YYYY-MM-DD'
            return date.fromisoformat(result[0])
        return None # Возвращаем None, если расписаний нет

async def set_resident_cleaning_stats(resident_id, room_id):
    """Обновляет статистику для ОДНОГО жителя (для ручного назначения)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE residents 
            SET consecutive_cleanings = consecutive_cleanings + 1, last_cleaned_room_id = ?
            WHERE id = ?
        """, (room_id, resident_id))
        await db.commit()

async def clear_latest_uncompleted_schedule():
    """
    Удаляет ВСЕ НЕЗАВЕРШЕННЫЕ записи
    для самой последней смены (по MAX(week_start_date)).
    Возвращает количество удаленных записей.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. Находим последнюю дату
        cursor = await db.execute("SELECT MAX(week_start_date) FROM schedule")
        latest_date_tuple = await cursor.fetchone()
        
        if not latest_date_tuple or not latest_date_tuple[0]:
            return 0 # Таблица пуста

        latest_date = latest_date_tuple[0]
        
        # 2. Удаляем незавершенные записи для этой даты
        cursor = await db.execute(
            "DELETE FROM schedule WHERE week_start_date = ? AND is_completed = FALSE",
            (latest_date,)
        )
        await db.commit()
        return cursor.rowcount

async def delete_schedule_by_date(date_to_delete):
    """
    (ДЛЯ ИСПРАВЛЕНИЯ /admin_force_assignment)
    Удаляет ВСЕ записи (выполненные и нет) для КОНКРЕТНОЙ даты.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM schedule WHERE week_start_date = ?", (date_to_delete,))
        await db.commit()

async def register_user(resident_id, telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE residents SET telegram_id = ? WHERE id = ?", (telegram_id, resident_id))
        await db.commit()

async def get_resident_by_tg_id(telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM residents WHERE telegram_id = ?", (telegram_id,))
        return await cursor.fetchone()

# --- Функции для планировщика ---
async def get_cleaning_candidates():
    """
    ИЗМЕНЕНО: Теперь выбирает ВСЕХ жителей, но сортирует их
    по количеству уборок подряд (по возрастанию).
    Это гарантирует, что мы всегда получим кандидатов,
    если жители вообще есть в БД.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM residents ORDER BY consecutive_cleanings ASC, RANDOM()")
        return await cursor.fetchall()

async def get_all_rooms():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM rooms")
        return await cursor.fetchall()

async def add_schedule_entry(resident_id, room_id, week_start_date):
    """Добавляет одну запись о дежурстве в БД и возвращает её ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO schedule (resident_id, room_id, week_start_date) VALUES (?, ?, ?)",
            (resident_id, room_id, week_start_date)
        )
        await db.commit()
        return cursor.lastrowid

async def update_resident_cleaning_stats(assigned_id_pairs, all_resident_ids):
    """Обновляет статистику уборок для всех жителей."""
    async with aiosqlite.connect(DB_NAME) as db:
        assigned_ids = {res_id for res_id, room_id in assigned_id_pairs}
        unassigned_ids = set(all_resident_ids) - assigned_ids

        for res_id in unassigned_ids:
            await db.execute("UPDATE residents SET consecutive_cleanings = 0 WHERE id = ?", (res_id,))
        
        for res_id, room_id in assigned_id_pairs:
            await db.execute("""
                UPDATE residents 
                SET consecutive_cleanings = consecutive_cleanings + 1, last_cleaned_room_id = ?
                WHERE id = ?
            """, (room_id, res_id))
        await db.commit()

async def get_all_resident_ids():
    """Возвращает ID всех жителей."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id FROM residents")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def is_schedule_empty():
    """Проверяет, пуста ли таблица с расписаниями."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(id) FROM schedule")
        count = await cursor.fetchone()
        return count[0] == 0

# --- Функции для уведомлений ---
async def get_uncompleted_duties_for_today():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.id, r.name as resident_name, rm.name as room_name, r.telegram_id
            FROM schedule s
            JOIN residents r ON s.resident_id = r.id
            JOIN rooms rm ON s.room_id = rm.id
            WHERE s.is_completed = FALSE AND date('now') >= s.week_start_date AND date('now') <= date(s.week_start_date, '+6 days')
        """)
        return await cursor.fetchall()

async def get_overdue_duties():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.id, r.name as resident_name, rm.name as room_name, r.telegram_id
            FROM schedule s
            JOIN residents r ON s.resident_id = r.id
            JOIN rooms rm ON s.room_id = rm.id
            WHERE s.is_completed = FALSE AND date('now') > date(s.week_start_date, '+6 days')
        """)
        return await cursor.fetchall()
        
# --- Функции для колбэков ---
async def complete_duty(schedule_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE schedule SET is_completed = TRUE WHERE id = ?", (schedule_id,))
        await db.commit()
        
async def get_duty_details_for_rating(schedule_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.id, r.telegram_id as cleaner_tg_id, rm.name as room_name
            FROM schedule s
            JOIN residents r ON s.resident_id = r.id
            JOIN rooms rm ON s.room_id = rm.id
            WHERE s.id = ?
        """, (schedule_id,))
        return await cursor.fetchone()

async def get_all_residents_for_rating():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT telegram_id FROM residents WHERE telegram_id IS NOT NULL")
        return await cursor.fetchall()

async def save_rating(schedule_id, rater_telegram_id, rating):
     async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO ratings (schedule_id, rater_telegram_id, rating_value) VALUES (?, ?, ?)",
            (schedule_id, rater_telegram_id, rating)
        )
        await db.commit()

# --- Функции для просмотра рейтинга ---
async def get_average_ratings():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT 
                res.name,
                AVG(rat.rating_value) as avg_rating,
                COUNT(rat.id) as total_ratings
            FROM residents res
            LEFT JOIN schedule sch ON res.id = sch.resident_id
            LEFT JOIN ratings rat ON sch.id = rat.schedule_id
            GROUP BY res.name
            ORDER BY avg_rating DESC
        """)
        return await cursor.fetchall()

# --- Функция для просмотра расписания ---
async def get_current_week_schedule():
    """Возвращает список дежурств для самой последней смены."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        
        # Сначала находим самую последнюю дату начала смены
        cursor = await db.execute("SELECT MAX(week_start_date) FROM schedule")
        latest_date_tuple = await cursor.fetchone()
        
        if not latest_date_tuple or not latest_date_tuple[0]:
            return [] # Возвращаем пустой список, если расписаний еще нет

        latest_date = latest_date_tuple[0]
        
        # Теперь получаем все записи для этой даты
        cursor = await db.execute("""
            SELECT 
                res.name as resident_name, 
                rm.name as room_name, 
                s.is_completed
            FROM schedule s
            JOIN residents res ON s.resident_id = res.id
            JOIN rooms rm ON s.room_id = rm.id
            WHERE s.week_start_date = ?
            ORDER BY rm.name
        """, (latest_date,))
        
        return await cursor.fetchall()

async def get_user_duty(telegram_id):
    """Получает информацию о дежурстве пользователя на текущей неделе."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.id, r.name as resident_name, rm.name as room_name, r.telegram_id
            FROM schedule s
            JOIN residents r ON s.resident_id = r.id
            JOIN rooms rm ON s.room_id = rm.id
            WHERE s.is_completed = FALSE 
            AND date('now') >= s.week_start_date 
            AND date('now') <= date(s.week_start_date, '+6 days')
            AND r.telegram_id = ?
        """, (telegram_id,))
        return await cursor.fetchone()