import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sqlite3

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8558881786:AAEs3jN0O_qTo3uifo67-pkKBhaaNnsjivI"

# Пароли
PASSWORDS = {
	"operator": "Operator007",
	"guide": "GuideLine0320",
	"guard": "Security2702",
	"super_guard": "SuperSecurity2705",
	"admin": "Admin501322"
}

# Заглушки для контента
STORY_TEXT = """
🎭 **ИСТОРИЯ**

**2099 год.**

Миру пришёл конец. Из-за глобального потепления океан затопил многие страны, а в некоторых — большую их часть. Это привело мир к хаосу и глобальному кризису, в результате чего началась **вторая кибер-мировая война**.

Кульминационным моментом стало то, что Китай, Россия, США, Франция, Иран и ряд других стран использовали свои ядерные боеголовки и уничтожили друг друга.

Даже если Казахстан не был участником всего этого ужаса, колоссальный эффект от войны повлиял на весь мир. Несколько взломанных ядерных ракет, к сожалению, ударили по ключевым городам Казахстана. Одним из них стал **Алматы** — столица культуры.

После того как Министерство обороны узнало, что на Алматы запущена ядерная ракета, и она достигнет цели через час, правительство собрало 32 лучших агента КНБ по Алматы, чтобы спасти одну очень ценную флешку, на которой находятся коды правительственного биткоин-кошелька и другие засекреченные данные.

К сожалению, она хранится в здании **КБТУ**, где когда-то находился старый бункер, ныне захваченный террористами **Red Hunters**.

Задача агентов — найти флешку, не попадаясь террористам, и добраться до точки эвакуации за ограниченное время — до того момента, как ядерная бомба уничтожит весь город.
"""

RULES_TEXT = """
📋 **ПРАВИЛА**

**Структура команды:**
Каждая команда состоит из 4 человек. У каждого участника есть своя роль и специализация.

**Роли:**
- **Медик 🏥** — может лечить других игроков с помощью аптечки
- **Взломщик-инженер 🔧** — может открывать запертые двери и использовать мультитул
- **Оператор-агент 📡** — имеет прямую связь с оператором
- **Мастер маскировки 🎭** — может маскироваться под террористов

**Система уровней:**
За выполнение заданий команда получает очки опыта. Команда решает, кому повысить уровень.

**Правила игры:**
- Если охранник видит вас — вы выбываете
- Медик может вылечить выбитого игрока
- У каждой роли есть 3 уровня с улучшенными способностями
- Время ограничено — 1 час до взрыва!
"""

# Роли и их описания
ROLES = {
	"medic": {
		"name": "Медик 🏥",
		"emoji": "🏥",
		"levels": {
			1: "Может излечить одного человека",
			2: "Может излечить двух человек",
			3: "Может излечить трёх человек"
		}
	},
	"engineer": {
		"name": "Взломщик-инженер 🔧",
		"emoji": "🔧",
		"levels": {
			1: "Может использовать фонарик",
			2: "Может открывать двери первого уровня",
			3: "Может открывать двери второго уровня"
		}
	},
	"agent": {
		"name": "Оператор-агент 📡",
		"emoji": "📡",
		"levels": {
			1: "Оператор отвечает да/нет, максимум 3 вопроса",
			2: "Оператор отвечает кратко, максимум 5 вопросов",
			3: "Оператор даёт подсказки, максимум 7 вопросов"
		}
	},
	"disguise": {
		"name": "Мастер маскировки 🎭",
		"emoji": "🎭",
		"levels": {
			1: "Может маскироваться синими вещами",
			2: "Может маскироваться синими и красными вещами",
			3: "Может маскироваться синими, красными и зелёными вещами"
		}
	}
}

# Главы
CHAPTERS = [
	{"id": 1, "name": "Глава 1: Проникновение в здание", "points": 300, "exp": 1,
	 "description": "Первое проникновение в здание КБТУ. Будьте осторожны!"},
	{"id": 2, "name": "Глава 2: Первый контакт", "points": 400, "exp": 1,
	 "description": "Встреча с первыми террористами."},
	{"id": 3, "name": "Глава 3: В логове врага", "points": 500, "exp": 1,
	 "description": "Проникновение вглубь здания."},
	{"id": 4, "name": "Глава 4: Поиск флешки", "points": 400, "exp": 1, "description": "Приближаемся к цели."},
	{"id": 5, "name": "Глава 5: Поворотный момент", "points": 500, "exp": 1,
	 "description": "Команда должна разделиться..."},
	{"id": 6, "name": "Финал: Эвакуация", "points": 600, "exp": 1, "description": "Последний рывок к спасению!"},
]

# Бонусные задания
BONUS_TASKS = [
	{"id": 1, "name": "Бонус: Секретный код"},
	{"id": 2, "name": "Бонус: Скрытая комната"},
	{"id": 3, "name": "Бонус: Артефакт прошлого"},
	{"id": 4, "name": "Бонус: Дневник террориста"},
	{"id": 5, "name": "Бонус: Запасная аптечка"},
]

GAME_DURATION_MINUTES = 60


# ==================== БАЗА ДАННЫХ ====================
class Database:
	def __init__ (self, db_name = "quest_bot.db"):
		self.db_name = db_name
		self.init_db ()

	def get_connection (self):
		return sqlite3.connect (self.db_name)

	def init_db (self):
		conn = self.get_connection ()
		cursor = conn.cursor ()

		cursor.execute ("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                team_name TEXT,
                first_name TEXT,
                last_name TEXT,
                player_role TEXT,
                player_level INTEGER DEFAULT 1,
                is_alive BOOLEAN DEFAULT 1,
                is_ready BOOLEAN DEFAULT 0,
                assigned_team TEXT
            )
        """)

		cursor.execute ("""
            CREATE TABLE IF NOT EXISTS teams (
                team_name TEXT PRIMARY KEY,
                exp_points INTEGER DEFAULT 0,
                main_points INTEGER DEFAULT 0,
                is_ready BOOLEAN DEFAULT 0
            )
        """)

		cursor.execute ("""
            CREATE TABLE IF NOT EXISTS progress (
                team_name TEXT,
                chapter_id INTEGER,
                status TEXT DEFAULT 'locked',
                PRIMARY KEY (team_name, chapter_id)
            )
        """)

		cursor.execute ("""
            CREATE TABLE IF NOT EXISTS bonus_progress (
                team_name TEXT,
                bonus_id INTEGER,
                completed BOOLEAN DEFAULT 0,
                PRIMARY KEY (team_name, bonus_id)
            )
        """)

		cursor.execute ("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT,
                sender_id INTEGER,
                sender_type TEXT,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT 0,
                is_free_question BOOLEAN DEFAULT 0
            )
        """)

		cursor.execute ("""
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT DEFAULT 'registration',
                start_time DATETIME,
                end_time DATETIME
            )
        """)

		cursor.execute ("INSERT OR IGNORE INTO game_state (id, status) VALUES (1, 'registration')")

		conn.commit ()
		conn.close ()


db = Database ()


# ==================== FSM STATES ====================
class RegistrationStates (StatesGroup):
	choosing_role = State ()
	entering_password = State ()
	entering_staff_name = State ()  # Для ввода имени персонала (операторы, охрана и т.д.)
	entering_team_name = State ()
	entering_first_name = State ()
	entering_last_name = State ()
	# Состояния для ввода данных остальных участников
	entering_teammate2_first = State ()
	entering_teammate2_last = State ()
	entering_teammate3_first = State ()
	entering_teammate3_last = State ()
	entering_teammate4_first = State ()
	entering_teammate4_last = State ()


class PreparationStates (StatesGroup):
	assigning_roles = State ()
	selecting_player = State ()


class ChatStates (StatesGroup):
	waiting_message = State ()


class AdminStates (StatesGroup):
	confirming_stop_game = State ()


# Словарь для хранения последних сообщений пользователей (для удаления)
user_last_messages: Dict[int, int] = {}


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_game_status ():
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT status, start_time, end_time FROM game_state WHERE id = 1")
	result = cursor.fetchone ()
	conn.close ()
	return result if result else ('registration', None, None)


def set_game_status (status, start_time = None, end_time = None):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	if start_time and end_time:
		cursor.execute (
			"UPDATE game_state SET status = ?, start_time = ?, end_time = ? WHERE id = 1",
			(status, start_time, end_time)
		)
	else:
		cursor.execute ("UPDATE game_state SET status = ? WHERE id = 1", (status,))
	conn.commit ()
	conn.close ()


def get_user_data (user_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT * FROM users WHERE user_id = ?", (user_id,))
	result = cursor.fetchone ()
	conn.close ()
	return result


def register_user (user_id, role, **kwargs):
	conn = db.get_connection ()
	cursor = conn.cursor ()

	columns = ["user_id", "role"]
	values = [user_id, role]

	for key, value in kwargs.items ():
		columns.append (key)
		values.append (value)

	placeholders = ", ".join (["?"] * len (values))
	columns_str = ", ".join (columns)

	cursor.execute (
		f"INSERT OR REPLACE INTO users ({columns_str}) VALUES ({placeholders})",
		values
	)
	conn.commit ()
	conn.close ()


def delete_user (user_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("DELETE FROM users WHERE user_id = ?", (user_id,))
	conn.commit ()
	conn.close ()


def reset_team_roles (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"UPDATE users SET player_role = NULL, player_level = 1 WHERE team_name = ? AND role = 'player'",
		(team_name,)
	)
	conn.commit ()
	conn.close ()


def get_team_data (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT * FROM teams WHERE team_name = ?", (team_name,))
	result = cursor.fetchone ()
	conn.close ()
	return result


def create_team (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"INSERT OR IGNORE INTO teams (team_name, exp_points, main_points) VALUES (?, 0, 0)",
		(team_name,)
	)

	for chapter in CHAPTERS:
		cursor.execute (
			"INSERT OR IGNORE INTO progress (team_name, chapter_id, status) VALUES (?, ?, 'locked')",
			(team_name, chapter["id"])
		)

	for bonus in BONUS_TASKS:
		cursor.execute (
			"INSERT OR IGNORE INTO bonus_progress (team_name, bonus_id, completed) VALUES (?, ?, 0)",
			(team_name, bonus["id"])
		)

	conn.commit ()
	conn.close ()


def get_team_members (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"SELECT user_id, first_name, last_name, player_role, player_level, is_alive FROM users WHERE team_name = ? AND role = 'player'",
		(team_name,)
	)
	results = cursor.fetchall ()
	conn.close ()
	return results


def get_all_teams ():
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT team_name, exp_points, main_points FROM teams ORDER BY main_points DESC, exp_points DESC")
	results = cursor.fetchall ()
	conn.close ()
	return results


def update_team_ready_status (team_name, is_ready):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE teams SET is_ready = ? WHERE team_name = ?", (is_ready, team_name))
	conn.commit ()
	conn.close ()


def update_user_ready_status (user_id, is_ready):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE users SET is_ready = ? WHERE user_id = ?", (is_ready, user_id))
	conn.commit ()
	conn.close ()


def assign_role_to_player (user_id, role_key):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE users SET player_role = ?, player_level = 1 WHERE user_id = ?", (role_key, user_id))
	conn.commit ()
	conn.close ()


def get_remaining_questions (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()

	cursor.execute (
		"SELECT player_level FROM users WHERE team_name = ? AND player_role = 'agent'",
		(team_name,)
	)
	result = cursor.fetchone ()

	if not result:
		conn.close ()
		return 0

	level = result[0]
	max_questions = {1: 3, 2: 5, 3: 7}.get (level, 3)

	cursor.execute (
		"SELECT COUNT(*) FROM messages WHERE team_name = ? AND sender_type = 'player' AND is_free_question = 0",
		(team_name,)
	)
	used = cursor.fetchone ()[0]
	conn.close ()

	return max (0, max_questions - used)


def add_message (team_name, sender_id, sender_type, message, is_free = False):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"INSERT INTO messages (team_name, sender_id, sender_type, message, is_free_question) VALUES (?, ?, ?, ?, ?)",
		(team_name, sender_id, sender_type, message, is_free)
	)
	conn.commit ()
	conn.close ()


def mark_messages_read (team_name, reader_type):
	conn = db.get_connection ()
	cursor = conn.cursor ()

	if reader_type == "player":
		sender_type = "operator"
	else:
		sender_type = "player"

	cursor.execute (
		"UPDATE messages SET is_read = 1 WHERE team_name = ? AND sender_type = ?",
		(team_name, sender_type)
	)
	conn.commit ()
	conn.close ()


def get_chat_messages (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"SELECT sender_type, message, timestamp, is_free_question FROM messages WHERE team_name = ? ORDER BY timestamp",
		(team_name,)
	)
	results = cursor.fetchall ()
	conn.close ()
	return results


def get_unread_count (team_name, user_type):
	conn = db.get_connection ()
	cursor = conn.cursor ()

	if user_type == "player":
		sender_type = "operator"
	else:
		sender_type = "player"

	cursor.execute (
		"SELECT COUNT(*) FROM messages WHERE team_name = ? AND sender_type = ? AND is_read = 0",
		(team_name, sender_type)
	)
	result = cursor.fetchone ()[0]
	conn.close ()
	return result


def get_assigned_team (user_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT assigned_team, team_name FROM users WHERE user_id = ?", (user_id,))
	result = cursor.fetchone ()
	conn.close ()
	if result:
		return result[0] if result[0] else result[1]
	return None


def assign_operator_to_team (user_id, team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE users SET assigned_team = ? WHERE user_id = ?", (team_name, user_id))
	conn.commit ()
	conn.close ()


def kill_player (user_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE users SET is_alive = 0 WHERE user_id = ?", (user_id,))
	conn.commit ()
	conn.close ()


def revive_player (user_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE users SET is_alive = 1 WHERE user_id = ?", (user_id,))
	conn.commit ()
	conn.close ()


def get_heal_capacity (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"SELECT player_level FROM users WHERE team_name = ? AND player_role = 'medic'",
		(team_name,)
	)
	result = cursor.fetchone ()
	conn.close ()
	return result[0] if result else 0


def upgrade_player (user_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE users SET player_level = player_level + 1 WHERE user_id = ? AND player_level < 3",
	                (user_id,))
	conn.commit ()
	conn.close ()


def add_exp_and_points (team_name, exp, points):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"UPDATE teams SET exp_points = exp_points + ?, main_points = main_points + ? WHERE team_name = ?",
		(exp, points, team_name)
	)
	conn.commit ()
	conn.close ()


def complete_chapter (team_name, chapter_id):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"UPDATE progress SET status = 'completed' WHERE team_name = ? AND chapter_id = ?",
		(team_name, chapter_id)
	)

	chapter = next ((c for c in CHAPTERS if c["id"] == chapter_id), None)
	if chapter:
		cursor.execute (
			"UPDATE teams SET exp_points = exp_points + ?, main_points = main_points + ? WHERE team_name = ?",
			(chapter["exp"], chapter["points"], team_name)
		)

	conn.commit ()
	conn.close ()


def get_team_progress (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"SELECT chapter_id, status FROM progress WHERE team_name = ?",
		(team_name,)
	)
	results = cursor.fetchall ()
	conn.close ()
	return {row[0]: row[1] for row in results}


def get_completed_bonuses (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"SELECT bonus_id FROM bonus_progress WHERE team_name = ? AND completed = 1",
		(team_name,)
	)
	results = cursor.fetchall ()
	conn.close ()
	return [row[0] for row in results]


def all_ready ():
	conn = db.get_connection ()
	cursor = conn.cursor ()

	cursor.execute ("SELECT COUNT(*) FROM teams WHERE is_ready = 0")
	teams_not_ready = cursor.fetchone ()[0]

	cursor.execute ("SELECT COUNT(*) FROM users WHERE role = 'operator' AND is_ready = 0")
	operators_not_ready = cursor.fetchone ()[0]

	conn.close ()
	return teams_not_ready == 0 and operators_not_ready == 0


def get_ready_status ():
	conn = db.get_connection ()
	cursor = conn.cursor ()

	cursor.execute ("SELECT team_name, is_ready FROM teams")
	teams = cursor.fetchall ()

	cursor.execute ("SELECT user_id, assigned_team, is_ready FROM users WHERE role = 'operator'")
	operators = cursor.fetchall ()

	conn.close ()
	return teams, operators


def get_time_remaining ():
	status, start_time, end_time = get_game_status ()

	if status != 'playing' or not end_time:
		return None

	end = datetime.fromisoformat (end_time)
	now = datetime.now ()

	if now >= end:
		return "00:00"

	remaining = end - now
	minutes = int (remaining.total_seconds () // 60)
	seconds = int (remaining.total_seconds () % 60)

	return f"{minutes:02d}:{seconds:02d}"


def get_available_teams_for_operator ():
	conn = db.get_connection ()
	cursor = conn.cursor ()

	cursor.execute ("""
        SELECT t.team_name
        FROM teams t
        WHERE t.team_name NOT IN (
            SELECT assigned_team FROM users WHERE role = 'operator' AND assigned_team IS NOT NULL
        )
    """)
	results = cursor.fetchall ()
	conn.close ()
	return [row[0] for row in results]


def get_all_staff ():
	"""Получить всех пользователей кроме игроков (операторы, охрана, гиды, админы)"""
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute (
		"SELECT user_id, role, first_name FROM users WHERE role != 'player' AND user_id > 0"
	)
	results = cursor.fetchall ()
	conn.close ()
	return results


def delete_team (team_name):
	conn = db.get_connection ()
	cursor = conn.cursor ()

	# Удаляем всех игроков команды
	cursor.execute ("DELETE FROM users WHERE team_name = ?", (team_name,))
	# Удаляем прогресс команды
	cursor.execute ("DELETE FROM progress WHERE team_name = ?", (team_name,))
	# Удаляем бонусный прогресс
	cursor.execute ("DELETE FROM bonus_progress WHERE team_name = ?", (team_name,))
	# Удаляем сообщения
	cursor.execute ("DELETE FROM messages WHERE team_name = ?", (team_name,))
	# Удаляем команду
	cursor.execute ("DELETE FROM teams WHERE team_name = ?", (team_name,))
	# Сбрасываем assigned_team у операторовезе
	cursor.execute ("UPDATE users SET assigned_team = NULL WHERE assigned_team = ?", (team_name,))

	conn.commit ()
	conn.close ()


def reset_game_to_registration ():
	conn = db.get_connection ()
	cursor = conn.cursor ()

	# Сбрасываем готовность команд
	cursor.execute ("UPDATE teams SET is_ready = 0")
	# Сбрасываем готовность операторов
	cursor.execute ("UPDATE users SET is_ready = 0 WHERE role = 'operator'")
	# Сбрасываем роли игроков
	cursor.execute ("UPDATE users SET player_role = NULL, player_level = 1 WHERE role = 'player'")

	conn.commit ()
	conn.close ()

	set_game_status ("registration")


def reset_game_to_preparation ():
	conn = db.get_connection ()
	cursor = conn.cursor ()

	# Сбрасываем готовность команд
	cursor.execute ("UPDATE teams SET is_ready = 0")
	# Сбрасываем готовность операторов
	cursor.execute ("UPDATE users SET is_ready = 0 WHERE role = 'operator'")
	# Воскрешаем всех игроков
	cursor.execute ("UPDATE users SET is_alive = 1 WHERE role = 'player'")
	# Сбрасываем очки и опыт
	cursor.execute ("UPDATE teams SET exp_points = 0, main_points = 0")
	# Сбрасываем прогресс глав
	cursor.execute ("UPDATE progress SET status = 'locked'")
	# Сбрасываем бонусы
	cursor.execute ("UPDATE bonus_progress SET completed = 0")
	# Удаляем сообщения
	cursor.execute ("DELETE FROM messages")

	conn.commit ()
	conn.close ()

	set_game_status ("preparation")


# ==================== КЛАВИАТУРЫ ====================
def get_start_keyboard (user_id):
	user_data = get_user_data (user_id)

	keyboard = InlineKeyboardMarkup (inline_keyboard = [])

	if user_data:
		keyboard.inline_keyboard.append ([
			InlineKeyboardButton (text = "▶️ Старт", callback_data = "start_game")
		])
		keyboard.inline_keyboard.append ([
			InlineKeyboardButton (text = "🔄 Сбросить регистрацию", callback_data = "reset_registration")
		])
	else:
		keyboard.inline_keyboard.append ([
			InlineKeyboardButton (text = "📝 Регистрация", callback_data = "register")
		])

	return keyboard


def get_role_selection_keyboard ():
	return InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "🎮 Игрок", callback_data = "role_player")],
		[InlineKeyboardButton (text = "👨‍💼 Оператор", callback_data = "role_operator")],
		[InlineKeyboardButton (text = "🗺️ Гид", callback_data = "role_guide")],
		[InlineKeyboardButton (text = "🛡️ Охрана", callback_data = "role_guard")],
		[InlineKeyboardButton (text = "⭐ Супер Охрана", callback_data = "role_super_guard")],
		[InlineKeyboardButton (text = "👑 Админ", callback_data = "role_admin")]
	])


def get_preparation_keyboard ():
	return InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "📖 История", callback_data = "prep_story")],
		[InlineKeyboardButton (text = "👥 Разделение на роли", callback_data = "prep_roles")],
		[InlineKeyboardButton (text = "📋 Правила", callback_data = "prep_rules")],
		[InlineKeyboardButton (text = "✅ Готов", callback_data = "prep_ready")]
	])


def get_back_keyboard ():
	return InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_prep")]
	])


def get_role_assignment_keyboard (team_name):
	members = get_team_members (team_name)
	assigned_roles = [m[3] for m in members if m[3]]

	keyboard = []
	for role_key, role_data in ROLES.items ():
		if role_key not in assigned_roles:
			keyboard.append ([
				InlineKeyboardButton (text = role_data["name"], callback_data = f"assign_role_{role_key}")
			])

	if len (assigned_roles) > 0:
		keyboard.append ([InlineKeyboardButton (text = "🔄 Сбросить роли", callback_data = "reset_roles")])

	if len (assigned_roles) == 4:
		keyboard.append ([InlineKeyboardButton (text = "✅ Готово", callback_data = "roles_done")])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_prep")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_player_selection_keyboard (team_name):
	members = get_team_members (team_name)
	keyboard = []

	for user_id, first_name, last_name, player_role, level, is_alive in members:
		if not player_role:
			keyboard.append ([
				InlineKeyboardButton (
					text = f"{first_name} {last_name}",
					callback_data = f"select_player_{user_id}"
				)
			])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_assign")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_main_menu_keyboard (user_id):
	user_data = get_user_data (user_id)
	if not user_data:
		return None

	role = user_data[1]
	team_name = get_assigned_team (user_id)

	keyboard = []

	if role == "player":
		time_str = get_time_remaining ()
		time_display = f"⏱ {time_str}" if time_str else "⏱ --:--"

		team_data = get_team_data (team_name)
		if team_data:
			exp = team_data[1]
			points = team_data[2]
			keyboard.append ([InlineKeyboardButton (text = f"{time_display} | 💎 Опыт: {exp} | 🏆 Очки: {points}",
			                                        callback_data = "noop")])

		keyboard.extend ([
			[InlineKeyboardButton (text = "📊 Таблица", callback_data = "menu_leaderboard")],
			[InlineKeyboardButton (text = "👥 Персонажи", callback_data = "menu_characters")],
			[InlineKeyboardButton (text = "📈 Прогресс", callback_data = "menu_progress")],
			[InlineKeyboardButton (text = "⬆️ Прокачка", callback_data = "menu_upgrade")]
		])

		unread = get_unread_count (team_name, "player")
		chat_text = f"📞 Оператор ({unread})" if unread > 0 else "📞 Оператор"
		keyboard.append ([InlineKeyboardButton (text = chat_text, callback_data = "menu_chat")])

	elif role == "operator":
		time_str = get_time_remaining ()
		time_display = f"⏱ {time_str}" if time_str else "⏱ --:--"
		keyboard.append ([InlineKeyboardButton (text = time_display, callback_data = "noop")])

		keyboard.extend ([
			[InlineKeyboardButton (text = "📊 Таблица", callback_data = "menu_leaderboard")],
			[InlineKeyboardButton (text = "📈 Прогресс", callback_data = "menu_progress")]
		])

		if team_name:
			unread = get_unread_count (team_name, "operator")
			chat_text = f"💬 Чат ({unread})" if unread > 0 else "💬 Чат"
			keyboard.append ([InlineKeyboardButton (text = chat_text, callback_data = "menu_chat")])

	elif role == "guide":
		time_str = get_time_remaining ()
		time_display = f"⏱ {time_str}" if time_str else "⏱ --:--"
		keyboard.append ([InlineKeyboardButton (text = time_display, callback_data = "noop")])

		keyboard.append ([
			InlineKeyboardButton (text = "✅ Прошёл главу", callback_data = "guide_complete_chapter")
		])

	elif role in ["guard", "super_guard"]:
		time_str = get_time_remaining ()
		time_display = f"⏱ {time_str}" if time_str else "⏱ --:--"
		keyboard.append ([InlineKeyboardButton (text = time_display, callback_data = "noop")])

		keyboard.append ([InlineKeyboardButton (text = "💀 Убить", callback_data = "guard_kill")])

		if role == "super_guard":
			keyboard.append ([InlineKeyboardButton (text = "💚 Воскресить", callback_data = "guard_revive")])

	elif role == "admin":
		time_str = get_time_remaining ()
		time_display = f"⏱ {time_str}" if time_str else "⏱ --:--"
		keyboard.append ([InlineKeyboardButton (text = time_display, callback_data = "noop")])

		keyboard.extend ([
			[InlineKeyboardButton (text = "📊 Таблица", callback_data = "menu_leaderboard")],
			[InlineKeyboardButton (text = "👥 Игроки", callback_data = "admin_players")],
			[InlineKeyboardButton (text = "⏹️ Остановить игру", callback_data = "admin_stop_game")]
		])

	return InlineKeyboardMarkup (inline_keyboard = keyboard) if keyboard else None


def get_team_selection_keyboard (teams_list):
	keyboard = []
	for team in teams_list:
		keyboard.append ([InlineKeyboardButton (text = team, callback_data = f"select_team_{team}")])
	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_player_list_keyboard (team_name, alive_only = False, dead_only = False):
	members = get_team_members (team_name)
	keyboard = []

	for user_id, first_name, last_name, player_role, level, is_alive in members:
		if alive_only and not is_alive:
			continue
		if dead_only and is_alive:
			continue

		role_emoji = ROLES[player_role]["emoji"] if player_role else "❓"
		status = "✅" if is_alive else "💀"
		keyboard.append ([
			InlineKeyboardButton (
				text = f"{status} {role_emoji} {first_name} {last_name}",
				callback_data = f"player_action_{user_id}"
			)
		])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_characters_keyboard (team_name):
	members = get_team_members (team_name)
	keyboard = []

	for user_id, first_name, last_name, player_role, level, is_alive in members:
		if player_role:
			role_data = ROLES[player_role]
			keyboard.append ([
				InlineKeyboardButton (
					text = f"{role_data['emoji']} {role_data['name']} - Ур.{level}",
					callback_data = f"char_{player_role}"
				)
			])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_upgrade_keyboard (team_name):
	members = get_team_members (team_name)
	team_data = get_team_data (team_name)

	if not team_data or team_data[1] == 0:
		return InlineKeyboardMarkup (inline_keyboard = [
			[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")]
		])

	keyboard = []
	for user_id, first_name, last_name, player_role, level, is_alive in members:
		if player_role and level < 3:
			role_data = ROLES[player_role]
			keyboard.append ([
				InlineKeyboardButton (
					text = f"{role_data['emoji']} {first_name} (Ур.{level} → {level + 1})",
					callback_data = f"upgrade_{user_id}"
				)
			])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_chapter_selection_keyboard ():
	keyboard = []
	for chapter in CHAPTERS:
		keyboard.append ([
			InlineKeyboardButton (text = chapter["name"], callback_data = f"chapter_{chapter['id']}")
		])
	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")])
	return InlineKeyboardMarkup (inline_keyboard = keyboard)


def get_operator_teams_keyboard ():
	teams = get_available_teams_for_operator ()
	keyboard = []

	for team in teams:
		keyboard.append ([InlineKeyboardButton (text = team, callback_data = f"op_select_{team}")])

	return InlineKeyboardMarkup (inline_keyboard = keyboard)


# ==================== ОСНОВНОЙ КОД БОТА ====================
logging.basicConfig (level = logging.INFO)
bot = Bot (token = BOT_TOKEN)
storage = MemoryStorage ()
dp = Dispatcher (storage = storage)
router = Router ()


# ==================== ОБРАБОТЧИКИ ====================

@router.message (CommandStart ())
async def cmd_start (message: Message):
	user_id = message.from_user.id
	user_data = get_user_data (user_id)

	if user_data:
		await message.answer (
			f"С возвращением! Ваша роль: {user_data[1]}",
			reply_markup = get_start_keyboard (user_id)
		)
	else:
		await message.answer (
			"🎮 Добро пожаловать в квест «2099»!\n\nДля начала зарегистрируйтесь:",
			reply_markup = get_start_keyboard (user_id)
		)


# ===== РЕГИСТРАЦИЯ =====
@router.callback_query (F.data == "register")
async def register_callback (callback: CallbackQuery, state: FSMContext):
	await callback.message.edit_text (
		"Выберите вашу роль:",
		reply_markup = get_role_selection_keyboard ()
	)
	await state.set_state (RegistrationStates.choosing_role)


@router.callback_query (F.data == "reset_registration")
async def reset_registration_callback (callback: CallbackQuery):
	user_id = callback.from_user.id
	user_data = get_user_data (user_id)

	if not user_data:
		await callback.answer ("Вы не зарегистрированы!")
		return

	game_status = get_game_status ()[0]

	if game_status != "registration":
		await callback.answer ("❌ Нельзя сбросить регистрацию после начала подготовки!", show_alert = True)
		return

	delete_user (user_id)

	await callback.answer ("🔄 Регистрация сброшена!")
	await callback.message.edit_text (
		"✅ Ваша регистрация сброшена.\n\nМожете зарегистрироваться заново:",
		reply_markup = get_start_keyboard (user_id)
	)


@router.callback_query (RegistrationStates.choosing_role, F.data.startswith ("role_"))
async def role_selected (callback: CallbackQuery, state: FSMContext):
	role = callback.data.replace ("role_", "")

	if role == "player":
		await state.update_data (role = role)
		await callback.message.edit_text ("Введите название вашей команды:")
		await state.set_state (RegistrationStates.entering_team_name)
	else:
		await state.update_data (role = role)
		await callback.message.edit_text ("Введите пароль:")
		await state.set_state (RegistrationStates.entering_password)


@router.message (RegistrationStates.entering_password)
async def password_entered (message: Message, state: FSMContext):
	data = await state.get_data ()
	role = data["role"]
	password = message.text

	correct_password = PASSWORDS.get (role)

	if password == correct_password:
		await message.answer ("Введите ваше имя:")
		await state.set_state (RegistrationStates.entering_staff_name)
	else:
		await message.answer (
			"❌ Неправильный пароль. Доступ запрещён.",
			reply_markup = get_role_selection_keyboard ()
		)
		await state.set_state (RegistrationStates.choosing_role)


@router.message (RegistrationStates.entering_staff_name)
async def staff_name_entered (message: Message, state: FSMContext):
	data = await state.get_data ()
	role = data["role"]
	staff_name = message.text.strip ()

	register_user (message.from_user.id, role, first_name = staff_name)

	role_names = {
		"operator": "Оператор",
		"guide": "Гид",
		"guard": "Охрана",
		"super_guard": "Супер Охрана",
		"admin": "Админ"
	}
	role_display = role_names.get (role, role)

	await message.answer (
		f"✅ Регистрация успешна!\n\nВы зарегистрированы как: {role_display}\nИмя: {staff_name}",
		reply_markup = get_start_keyboard (message.from_user.id)
	)
	await state.clear ()


@router.message (RegistrationStates.entering_team_name)
async def team_name_entered (message: Message, state: FSMContext):
	team_name = message.text.strip ()
	await state.update_data (team_name = team_name)

	create_team (team_name)

	await message.answer ("Введите ваше имя:")
	await state.set_state (RegistrationStates.entering_first_name)


@router.message (RegistrationStates.entering_first_name)
async def first_name_entered (message: Message, state: FSMContext):
	first_name = message.text.strip ()
	await state.update_data (first_name = first_name)
	await message.answer ("Введите вашу фамилию:")
	await state.set_state (RegistrationStates.entering_last_name)


@router.message (RegistrationStates.entering_last_name)
async def last_name_entered (message: Message, state: FSMContext):
	last_name = message.text.strip ()
	await state.update_data (last_name = last_name)

	await message.answer (
		"👥 Теперь введите данные остальных участников команды.\n\n"
		"**Участник 2** - Введите имя:"
	)
	await state.set_state (RegistrationStates.entering_teammate2_first)


@router.message (RegistrationStates.entering_teammate2_first)
async def teammate2_first_entered (message: Message, state: FSMContext):
	await state.update_data (teammate2_first = message.text.strip ())
	await message.answer ("**Участник 2** - Введите фамилию:")
	await state.set_state (RegistrationStates.entering_teammate2_last)


@router.message (RegistrationStates.entering_teammate2_last)
async def teammate2_last_entered (message: Message, state: FSMContext):
	await state.update_data (teammate2_last = message.text.strip ())
	await message.answer ("**Участник 3** - Введите имя:")
	await state.set_state (RegistrationStates.entering_teammate3_first)


@router.message (RegistrationStates.entering_teammate3_first)
async def teammate3_first_entered (message: Message, state: FSMContext):
	await state.update_data (teammate3_first = message.text.strip ())
	await message.answer ("**Участник 3** - Введите фамилию:")
	await state.set_state (RegistrationStates.entering_teammate3_last)


@router.message (RegistrationStates.entering_teammate3_last)
async def teammate3_last_entered (message: Message, state: FSMContext):
	await state.update_data (teammate3_last = message.text.strip ())
	await message.answer ("**Участник 4** - Введите имя:")
	await state.set_state (RegistrationStates.entering_teammate4_first)


@router.message (RegistrationStates.entering_teammate4_first)
async def teammate4_first_entered (message: Message, state: FSMContext):
	await state.update_data (teammate4_first = message.text.strip ())
	await message.answer ("**Участник 4** - Введите фамилию:")
	await state.set_state (RegistrationStates.entering_teammate4_last)


@router.message (RegistrationStates.entering_teammate4_last)
async def teammate4_last_entered (message: Message, state: FSMContext):
	teammate4_last = message.text.strip ()
	data = await state.get_data ()

	team_name = data["team_name"]

	# Регистрируем капитана (первый участник с user_id)
	register_user (
		message.from_user.id,
		"player",
		team_name = team_name,
		first_name = data["first_name"],
		last_name = data["last_name"]
	)

	# Регистрируем остальных участников (без user_id - генерируем уникальные отрицательные id)
	conn = db.get_connection ()
	cursor = conn.cursor ()

	# Генерируем уникальные ID для остальных участников
	import time
	base_id = -int (time.time () * 1000)

	teammates = [
		(base_id - 1, data["teammate2_first"], data["teammate2_last"]),
		(base_id - 2, data["teammate3_first"], data["teammate3_last"]),
		(base_id - 3, data["teammate4_first"], teammate4_last)
	]

	for fake_id, first, last in teammates:
		cursor.execute (
			"INSERT INTO users (user_id, role, team_name, first_name, last_name) VALUES (?, 'player', ?, ?, ?)",
			(fake_id, team_name, first, last)
		)

	conn.commit ()
	conn.close ()

	# Формируем сообщение с составом команды
	text = f"✅ Регистрация команды завершена!\n\n"
	text += f"**Команда: {team_name}**\n\n"
	text += f"1. {data['first_name']} {data['last_name']} (капитан)\n"
	text += f"2. {data['teammate2_first']} {data['teammate2_last']}\n"
	text += f"3. {data['teammate3_first']} {data['teammate3_last']}\n"
	text += f"4. {data['teammate4_first']} {teammate4_last}"

	await message.answer (text, reply_markup = get_start_keyboard (message.from_user.id))
	await state.clear ()


# ===== СТАРТ ИГРЫ =====
@router.callback_query (F.data == "start_game")
async def start_game_callback (callback: CallbackQuery):
	user_id = callback.from_user.id
	user_data = get_user_data (user_id)

	if not user_data:
		await callback.answer ("Сначала зарегистрируйтесь!")
		return

	role = user_data[1]
	game_status = get_game_status ()[0]

	# Для админа
	if role == "admin":
		if game_status == "registration":
			teams, operators = get_ready_status ()

			text = "📋 Статус регистрации:\n\nКоманды:\n"
			for team_name, is_ready in teams:
				text += f"• {team_name}\n"

			text += f"\nОператоры: {len (operators)}\n"

			keyboard = [
				[InlineKeyboardButton (text = "🚀 Начать подготовку", callback_data = "admin_start_prep")]
			]
			if teams:
				keyboard.append ([InlineKeyboardButton (text = "🗑️ Удалить команду", callback_data = "admin_delete_teams")])

			# Кнопка удаления персонала
			staff = get_all_staff ()
			if staff:
				keyboard.append ([InlineKeyboardButton (text = "👤 Удалить пользователя", callback_data = "admin_delete_users")])

			await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))

		elif game_status == "preparation":
			teams, operators = get_ready_status ()

			text = "📋 Статус готовности:\n\nКоманды:\n"
			for team_name, is_ready in teams:
				status = "✅" if is_ready else "⏳"
				text += f"{status} {team_name}\n"

			text += "\nОператоры:\n"
			for op_id, assigned, is_ready in operators:
				status = "✅" if is_ready else "⏳"
				team = assigned if assigned else "не выбрана"
				text += f"{status} Оператор (команда: {team})\n"

			keyboard = []
			if all_ready ():
				keyboard.append ([InlineKeyboardButton (text = "🚀 Начать игру", callback_data = "admin_start")])
			keyboard.append ([InlineKeyboardButton (text = "◀️ Отменить подготовку", callback_data = "admin_cancel_prep")])

			await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))

		elif game_status == "playing":
			await callback.message.edit_text (
				"🎮 Игра началась!",
				reply_markup = get_main_menu_keyboard (user_id)
			)

	# Для операторов
	elif role == "operator":
		if game_status == "registration":
			await callback.message.edit_text ("⏳ Ожидание начала подготовки...")

		elif game_status == "preparation":
			assigned = get_assigned_team (user_id)
			if not assigned:
				teams = get_available_teams_for_operator ()
				if teams:
					await callback.message.edit_text (
						"Выберите команду для курирования:",
						reply_markup = get_operator_teams_keyboard ()
					)
				else:
					await callback.message.edit_text ("❌ Все команды уже заняты другими операторами.")
			else:
				keyboard = InlineKeyboardMarkup (inline_keyboard = [
					[InlineKeyboardButton (text = "✅ Готов", callback_data = "operator_ready")]
				])
				await callback.message.edit_text (
					f"Вы курируете команду: {assigned}\n\nНажмите готов, когда будете готовы.",
					reply_markup = keyboard
				)

		elif game_status == "playing":
			await callback.message.edit_text (
				"🎮 Игра началась!",
				reply_markup = get_main_menu_keyboard (user_id)
			)

	# Для гидов и охраны
	elif role in ["guide", "guard", "super_guard"]:
		if game_status in ["registration", "preparation"]:
			await callback.message.edit_text ("⏳ Игра ещё не началась...")
		else:
			await callback.message.edit_text (
				"🎮 Игра началась!",
				reply_markup = get_main_menu_keyboard (user_id)
			)

	# Для игроков
	elif role == "player":
		if game_status == "registration":
			await callback.message.edit_text ("⏳ Ожидание начала подготовки...")

		elif game_status == "preparation":
			await callback.message.edit_text (
				"🎯 ПОДГОТОВКА К МИССИИ\n\nИзучите информацию и распределите роли!",
				reply_markup = get_preparation_keyboard ()
			)

		elif game_status == "playing":
			team_name = user_data[2]
			members = get_team_members (team_name)

			text = f"🎮 Команда: {team_name}\n\nСостав:\n"
			for uid, fname, lname, prole, lvl, alive in members:
				if prole:
					role_data = ROLES[prole]
					status = "✅" if alive else "💀"
					text += f"{status} {role_data['emoji']} {fname} {lname} (Ур.{lvl})\n"

			await callback.message.edit_text (
				text,
				reply_markup = get_main_menu_keyboard (user_id)
			)


# ===== АДМИН НАЧИНАЕТ ПОДГОТОВКУ =====
@router.callback_query (F.data == "admin_start_prep")
async def admin_start_prep_callback (callback: CallbackQuery):
	set_game_status ("preparation")
	await callback.answer ("✅ Подготовка началась!")
	await callback.message.edit_text ("✅ Этап подготовки запущен!")

	# Уведомляем всех
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT user_id FROM users WHERE role IN ('player', 'operator')")
	users = cursor.fetchall ()
	conn.close ()

	for user in users:
		try:
			await bot.send_message (
				user[0],
				"🎯 ПОДГОТОВКА К МИССИИ НАЧАЛАСЬ!\n\nНажмите /start для продолжения."
			)
		except:
			pass


# ===== ПОДГОТОВКА =====
@router.callback_query (F.data == "prep_story")
async def prep_story (callback: CallbackQuery):
	await callback.message.edit_text (
		STORY_TEXT,
		reply_markup = get_back_keyboard ()
	)


@router.callback_query (F.data == "prep_rules")
async def prep_rules (callback: CallbackQuery):
	await callback.message.edit_text (
		RULES_TEXT,
		reply_markup = get_back_keyboard ()
	)


@router.callback_query (F.data == "back_to_prep")
async def back_to_prep (callback: CallbackQuery, state: FSMContext):
	await state.clear ()
	await callback.message.edit_text (
		"🎯 ПОДГОТОВКА К МИССИИ\n\nИзучите информацию и распределите роли!",
		reply_markup = get_preparation_keyboard ()
	)


@router.callback_query (F.data == "prep_roles")
async def prep_roles (callback: CallbackQuery, state: FSMContext):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	members = get_team_members (team_name)

	text = "👥 Распределение ролей\n\n"

	for uid, fname, lname, prole, lvl, alive in members:
		if prole:
			role_data = ROLES[prole]
			text += f"{role_data['emoji']} {role_data['name']}: {fname} {lname}\n"

	text += "\nВыберите роль для назначения:"

	await callback.message.edit_text (
		text,
		reply_markup = get_role_assignment_keyboard (team_name)
	)
	await state.set_state (PreparationStates.assigning_roles)


@router.callback_query (PreparationStates.assigning_roles, F.data.startswith ("assign_role_"))
async def assign_role (callback: CallbackQuery, state: FSMContext):
	role_key = callback.data.replace ("assign_role_", "")
	await state.update_data (selected_role = role_key)

	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	role_data = ROLES[role_key]

	text = f"👤 Выберите игрока для роли:\n\n{role_data['name']}\n\n"
	text += f"📝 {role_data['levels'][1]}"

	await callback.message.edit_text (
		text,
		reply_markup = get_player_selection_keyboard (team_name)
	)
	await state.set_state (PreparationStates.selecting_player)


@router.callback_query (PreparationStates.selecting_player, F.data.startswith ("select_player_"))
async def select_player (callback: CallbackQuery, state: FSMContext):
	player_id = int (callback.data.replace ("select_player_", ""))
	data = await state.get_data ()
	role_key = data["selected_role"]

	assign_role_to_player (player_id, role_key)

	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	await callback.answer (f"✅ Роль назначена!")

	members = get_team_members (team_name)

	text = "👥 Распределение ролей\n\n"

	for uid, fname, lname, prole, lvl, alive in members:
		if prole:
			role_data = ROLES[prole]
			text += f"{role_data['emoji']} {role_data['name']}: {fname} {lname}\n"

	text += "\nВыберите роль для назначения:"

	await callback.message.edit_text (
		text,
		reply_markup = get_role_assignment_keyboard (team_name)
	)
	await state.set_state (PreparationStates.assigning_roles)


@router.callback_query (F.data == "back_to_assign")
async def back_to_assign (callback: CallbackQuery, state: FSMContext):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	members = get_team_members (team_name)

	text = "👥 Распределение ролей\n\n"

	for uid, fname, lname, prole, lvl, alive in members:
		if prole:
			role_data = ROLES[prole]
			text += f"{role_data['emoji']} {role_data['name']}: {fname} {lname}\n"

	text += "\nВыберите роль для назначения:"

	await callback.message.edit_text (
		text,
		reply_markup = get_role_assignment_keyboard (team_name)
	)
	await state.set_state (PreparationStates.assigning_roles)


@router.callback_query (F.data == "reset_roles")
async def reset_roles_callback (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	reset_team_roles (team_name)

	await callback.answer ("🔄 Роли сброшены!")

	text = "👥 Распределение ролей\n\nВсе роли сброшены. Выберите роль для назначения:"

	await callback.message.edit_text (
		text,
		reply_markup = get_role_assignment_keyboard (team_name)
	)


@router.callback_query (F.data == "roles_done")
async def roles_done (callback: CallbackQuery, state: FSMContext):
	await state.clear ()
	await callback.message.edit_text (
		"🎯 ПОДГОТОВКА К МИССИИ\n\nИзучите информацию и распределите роли!",
		reply_markup = get_preparation_keyboard ()
	)


@router.callback_query (F.data == "prep_ready")
async def prep_ready (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	members = get_team_members (team_name)
	unassigned = [m for m in members if not m[3]]

	if unassigned:
		await callback.answer ("❌ Сначала назначьте роли всем участникам!", show_alert = True)
		return

	update_team_ready_status (team_name, True)
	await callback.answer ("✅ Команда готова!")
	await callback.message.edit_text (
		f"✅ Команда {team_name} готова к игре!\n\nОжидание других команд..."
	)


# ===== ОПЕРАТОР ВЫБИРАЕТ КОМАНДУ =====
@router.callback_query (F.data.startswith ("op_select_"))
async def operator_select_team (callback: CallbackQuery):
	team_name = callback.data.replace ("op_select_", "")
	user_id = callback.from_user.id

	assign_operator_to_team (user_id, team_name)

	keyboard = InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "✅ Готов", callback_data = "operator_ready")]
	])

	await callback.message.edit_text (
		f"Вы курируете команду: {team_name}\n\nНажмите готов, когда будете готовы.",
		reply_markup = keyboard
	)


@router.callback_query (F.data == "operator_ready")
async def operator_ready (callback: CallbackQuery):
	update_user_ready_status (callback.from_user.id, True)
	await callback.answer ("✅ Вы готовы!")
	await callback.message.edit_text ("✅ Вы готовы к игре!\n\nОжидание других операторов...")


# ===== АДМИН НАЧИНАЕТ ИГРУ =====
@router.callback_query (F.data == "admin_start")
async def admin_start_game (callback: CallbackQuery):
	if not all_ready ():
		await callback.answer ("❌ Не все команды и операторы готовы!", show_alert = True)
		return

	start_time = datetime.now ()
	end_time = start_time + timedelta (minutes = GAME_DURATION_MINUTES)

	set_game_status ("playing", start_time.isoformat (), end_time.isoformat ())

	await callback.answer ("🚀 Игра началась!")
	await callback.message.edit_text (
		f"🎮 ИГРА НАЧАЛАСЬ!\n\n⏱ Время: {GAME_DURATION_MINUTES} минут\n\nУдачи командам!",
		reply_markup = get_main_menu_keyboard (callback.from_user.id)
	)


# ===== ГЛАВНОЕ МЕНЮ - ТАБЛИЦА ЛИДЕРОВ =====
@router.callback_query (F.data == "menu_leaderboard")
async def show_leaderboard (callback: CallbackQuery):
	teams = get_all_teams ()

	text = "🏆 ТАБЛИЦА ЛИДЕРОВ\n\n"

	for i, (team_name, exp, points) in enumerate (teams, 1):
		medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get (i, f"{i}.")
		text += f"{medal} {team_name}\n"
		text += f"   💎 Опыт: {exp} | 🏆 Очки: {points}\n\n"

	keyboard = InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")]
	])

	await callback.message.edit_text (text, reply_markup = keyboard)


# ===== ПЕРСОНАЖИ =====
@router.callback_query (F.data == "menu_characters")
async def show_characters (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	await callback.message.edit_text (
		"👥 Выберите персонажа:",
		reply_markup = get_characters_keyboard (team_name)
	)


@router.callback_query (F.data.startswith ("char_"))
async def show_character_info (callback: CallbackQuery):
	role_key = callback.data.replace ("char_", "")
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	members = get_team_members (team_name)
	player_info = next ((m for m in members if m[3] == role_key), None)

	if not player_info:
		await callback.answer ("Роль не найдена")
		return

	uid, fname, lname, prole, lvl, alive = player_info
	role_data = ROLES[role_key]

	text = f"{role_data['emoji']} {role_data['name']}\n\n"
	text += f"Игрок: {fname} {lname}\n"
	text += f"Уровень: {lvl}\n\n"
	text += f"Способность: {role_data['levels'][lvl]}\n"

	keyboard = []

	if role_key == "medic" and alive:
		dead_players = [m for m in members if not m[5]]
		if dead_players:
			keyboard.append ([InlineKeyboardButton (text = "💊 Вылечить", callback_data = "medic_heal")])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "menu_characters")])

	await callback.message.edit_text (
		text,
		reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard)
	)


@router.callback_query (F.data == "medic_heal")
async def medic_heal (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	capacity = get_heal_capacity (team_name)
	dead_players = [m for m in get_team_members (team_name) if not m[5]]

	if not dead_players:
		await callback.answer ("Нет выбитых игроков")
		return

	text = f"💊 Лечение (можно вылечить {capacity} чел.)\n\nВыберите игрока:"

	keyboard = []
	for uid, fname, lname, prole, lvl, alive in dead_players[:capacity]:
		role_emoji = ROLES[prole]["emoji"] if prole else "❓"
		keyboard.append ([
			InlineKeyboardButton (
				text = f"💀 {role_emoji} {fname} {lname}",
				callback_data = f"heal_{uid}"
			)
		])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "char_medic")])

	await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))


@router.callback_query (F.data.startswith ("heal_"))
async def heal_player (callback: CallbackQuery):
	player_id = int (callback.data.replace ("heal_", ""))
	revive_player (player_id)

	await callback.answer ("✅ Игрок вылечен!")

	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]

	await callback.message.edit_text (
		"👥 Выберите персонажа:",
		reply_markup = get_characters_keyboard (team_name)
	)


# ===== ПРОГРЕСС =====
@router.callback_query (F.data == "menu_progress")
async def show_progress (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = get_assigned_team (callback.from_user.id)

	if not team_name:
		await callback.answer ("Команда не найдена")
		return

	progress = get_team_progress (team_name)
	completed_bonuses = get_completed_bonuses (team_name)

	text = "📈 ПРОГРЕСС\n\nГлавы:\n"

	for chapter in CHAPTERS:
		status = progress.get (chapter["id"], "locked")

		if status == "locked":
			text += f"🔒 {chapter['name']}\n"
		elif status == "completed":
			text += f"✅ {chapter['name']}\n"
		else:
			text += f"📍 {chapter['name']}\n"

	text += f"\nБонусные задания: ({len (completed_bonuses)}/{len (BONUS_TASKS)})\n"

	for bonus in BONUS_TASKS:
		if bonus["id"] in completed_bonuses:
			text += f"✅ {bonus['name']}\n"
		else:
			text += f"⏳ {bonus['name']}\n"

	keyboard = InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "ℹ️ Информация о главе", callback_data = "chapter_info")],
		[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")]
	])

	await callback.message.edit_text (text, reply_markup = keyboard)


@router.callback_query (F.data == "chapter_info")
async def chapter_info (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = get_assigned_team (callback.from_user.id)

	progress = get_team_progress (team_name)

	current_chapter = None
	for chapter in CHAPTERS:
		if progress.get (chapter["id"], "locked") == "completed":
			continue
		current_chapter = chapter
		break

	if not current_chapter:
		current_chapter = CHAPTERS[-1]

	text = f"ℹ️ {current_chapter['name']}\n\n"
	text += f"{current_chapter.get ('description', 'Описание отсутствует.')}\n\n"
	text += f"🏆 Награда: {current_chapter['points']} очков\n"
	text += f"💎 Опыт: {current_chapter['exp']}"

	keyboard = InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "◀️ Назад", callback_data = "menu_progress")]
	])

	await callback.message.edit_text (text, reply_markup = keyboard)


# ===== ПРОКАЧКА =====
@router.callback_query (F.data == "menu_upgrade")
async def show_upgrade_menu (callback: CallbackQuery):
	user_data = get_user_data (callback.from_user.id)
	team_name = user_data[2]
	team_data = get_team_data (team_name)

	exp = team_data[1] if team_data else 0

	text = f"⬆️ ПРОКАЧКА ПЕРСОНАЖЕЙ\n\n💎 Доступно опыта: {exp}\n\n"

	if exp == 0:
		text += "Выполняйте задания, чтобы получить опыт!"
		keyboard = InlineKeyboardMarkup (inline_keyboard = [
			[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")]
		])
	else:
		text += "Выберите персонажа для прокачки:"
		keyboard = get_upgrade_keyboard (team_name)

	await callback.message.edit_text (text, reply_markup = keyboard)


@router.callback_query (F.data.startswith ("upgrade_"))
async def upgrade_character (callback: CallbackQuery):
	user_id_to_upgrade = int (callback.data.replace ("upgrade_", ""))

	player_data = get_user_data (user_id_to_upgrade)
	team_name = player_data[2]
	team_data = get_team_data (team_name)

	if team_data[1] < 1:
		await callback.answer ("Недостаточно опыта!", show_alert = True)
		return

	upgrade_player (user_id_to_upgrade)

	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("UPDATE teams SET exp_points = exp_points - 1 WHERE team_name = ?", (team_name,))
	conn.commit ()
	conn.close ()

	await callback.answer ("✅ Персонаж прокачан!")

	team_data = get_team_data (team_name)
	exp = team_data[1]

	text = f"⬆️ ПРОКАЧКА ПЕРСОНАЖЕЙ\n\n💎 Доступно опыта: {exp}\n\n"

	if exp == 0:
		text += "Выполняйте задания, чтобы получить опыт!"
		keyboard = InlineKeyboardMarkup (inline_keyboard = [
			[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")]
		])
	else:
		text += "Выберите персонажа для прокачки:"
		keyboard = get_upgrade_keyboard (team_name)

	await callback.message.edit_text (text, reply_markup = keyboard)


# ===== ЧАТ С ОПЕРАТОРОМ =====
@router.callback_query (F.data == "menu_chat")
async def open_chat (callback: CallbackQuery, state: FSMContext):
	user_data = get_user_data (callback.from_user.id)
	role = user_data[1]
	team_name = get_assigned_team (callback.from_user.id)

	mark_messages_read (team_name, role)

	messages = get_chat_messages (team_name)

	if role == "player":
		remaining = get_remaining_questions (team_name)
		text = f"📞 ЧАТ С ОПЕРАТОРОМ\n\n💬 Осталось вопросов: {remaining}\n\n"
	else:
		text = f"💬 ЧАТ С КОМАНДОЙ {team_name}\n\n"

	if messages:
		for sender_type, message, timestamp, is_free in messages[-10:]:
			sender = "🎮 Команда" if sender_type == "player" else "👨‍💼 Оператор"
			free_mark = " 🆓" if is_free else ""
			text += f"{sender}{free_mark}: {message}\n"
	else:
		text += "Сообщений пока нет."

	text += "\n💬 Напишите сообщение:"

	keyboard = InlineKeyboardMarkup (inline_keyboard = [])

	if role == "operator":
		keyboard.inline_keyboard.append ([
			InlineKeyboardButton (text = "❓ Задать бесплатный вопрос", callback_data = "operator_free_question")
		])

	keyboard.inline_keyboard.append ([
		InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")
	])

	await callback.message.edit_text (text, reply_markup = keyboard)
	await state.set_state (ChatStates.waiting_message)
	await state.update_data (team_name = team_name, role = role)


@router.callback_query (F.data == "operator_free_question")
async def operator_free_question (callback: CallbackQuery, state: FSMContext):
	await callback.answer ("Следующий вопрос от команды будет бесплатным!")
	await state.update_data (next_is_free = True)


@router.message (ChatStates.waiting_message)
async def receive_chat_message (message: Message, state: FSMContext):
	data = await state.get_data ()
	team_name = data["team_name"]
	role = data["role"]
	is_free = data.get ("next_is_free", False)

	if role == "player" and not is_free:
		remaining = get_remaining_questions (team_name)
		if remaining <= 0:
			await message.answer ("❌ У вас закончились вопросы!")
			return

	add_message (team_name, message.from_user.id, role, message.text, is_free)

	await message.answer ("✅ Сообщение отправлено!")

	conn = db.get_connection ()
	cursor = conn.cursor ()

	if role == "player":
		cursor.execute ("SELECT user_id FROM users WHERE assigned_team = ? AND role = 'operator'", (team_name,))
		operator = cursor.fetchone ()
		if operator:
			try:
				await bot.send_message (
					operator[0],
					f"💬 Новое сообщение от команды {team_name}:\n\n{message.text}"
				)
			except:
				pass
	else:
		cursor.execute ("SELECT user_id FROM users WHERE team_name = ? AND player_role = 'agent'", (team_name,))
		agent = cursor.fetchone ()
		if agent:
			try:
				await bot.send_message (
					agent[0],
					f"📞 Сообщение от оператора:\n\n{message.text}"
				)
			except:
				pass

	conn.close ()

	await state.update_data (next_is_free = False)


# ===== ГИДЫ - ЗАВЕРШЕНИЕ ГЛАВ =====
@router.callback_query (F.data == "guide_complete_chapter")
async def guide_select_chapter (callback: CallbackQuery):
	text = "✅ Выберите главу, которую команда прошла:"

	await callback.message.edit_text (
		text,
		reply_markup = get_chapter_selection_keyboard ()
	)


@router.callback_query (F.data.startswith ("chapter_"))
async def guide_select_team_for_chapter (callback: CallbackQuery, state: FSMContext):
	chapter_id = int (callback.data.replace ("chapter_", ""))
	await state.update_data (selected_chapter = chapter_id)

	teams = get_all_teams ()
	team_names = [t[0] for t in teams]

	chapter = next ((c for c in CHAPTERS if c["id"] == chapter_id), None)

	text = f"✅ {chapter['name']}\n\nВыберите команду:"

	await callback.message.edit_text (
		text,
		reply_markup = get_team_selection_keyboard (team_names)
	)


@router.callback_query (F.data.startswith ("select_team_"))
async def guide_complete_for_team (callback: CallbackQuery, state: FSMContext):
	team_name = callback.data.replace ("select_team_", "")
	data = await state.get_data ()
	chapter_id = data.get ("selected_chapter")

	if not chapter_id:
		await callback.answer ("Ошибка: глава не выбрана")
		return

	complete_chapter (team_name, chapter_id)

	chapter = next ((c for c in CHAPTERS if c["id"] == chapter_id), None)

	await callback.answer ("✅ Глава отмечена как выполненная!")
	await callback.message.edit_text (
		f"✅ Команда {team_name} завершила:\n{chapter['name']}\n\n"
		f"🏆 +{chapter['points']} очков\n💎 +{chapter['exp']} опыта"
	)

	await state.clear ()

	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT user_id FROM users WHERE team_name = ? AND role = 'player'", (team_name,))
	players = cursor.fetchall ()
	conn.close ()

	for player in players:
		try:
			await bot.send_message (
				player[0],
				f"🎉 Ваша команда завершила:\n{chapter['name']}\n\n"
				f"🏆 +{chapter['points']} очков\n💎 +{chapter['exp']} опыта"
			)
		except:
			pass


# ===== ОХРАНА - УБИЙСТВО =====
@router.callback_query (F.data == "guard_kill")
async def guard_select_team_to_kill (callback: CallbackQuery):
	teams = get_all_teams ()
	team_names = [t[0] for t in teams]

	text = "💀 УБИТЬ ИГРОКА\n\nВыберите команду:"

	await callback.message.edit_text (
		text,
		reply_markup = get_team_selection_keyboard (team_names)
	)


@router.callback_query (F.data.startswith ("select_team_"))
async def guard_select_player_to_kill (callback: CallbackQuery, state: FSMContext):
	team_name = callback.data.replace ("select_team_", "")
	await state.update_data (selected_team = team_name, action = "kill")

	text = f"💀 Команда: {team_name}\n\nВыберите игрока:"

	await callback.message.edit_text (
		text,
		reply_markup = get_player_list_keyboard (team_name, alive_only = True)
	)


@router.callback_query (F.data.startswith ("player_action_"))
async def guard_execute_action (callback: CallbackQuery, state: FSMContext):
	player_id = int (callback.data.replace ("player_action_", ""))
	data = await state.get_data ()
	action = data.get ("action")
	team_name = data.get ("selected_team")

	if action == "kill":
		kill_player (player_id)
		await callback.answer ("💀 Игрок убит!")

		try:
			await bot.send_message (player_id, "💀 Вас убила охрана! Ждите медика...")
		except:
			pass

	elif action == "revive":
		revive_player (player_id)
		await callback.answer ("💚 Игрок воскрешён!")

		try:
			await bot.send_message (player_id, "💚 Вы воскрешены!")
		except:
			pass

	await state.clear ()

	user_data = get_user_data (callback.from_user.id)
	await callback.message.edit_text (
		"✅ Действие выполнено!",
		reply_markup = get_main_menu_keyboard (callback.from_user.id)
	)


# ===== СУПЕР ОХРАНА - ВОСКРЕШЕНИЕ =====
@router.callback_query (F.data == "guard_revive")
async def guard_select_team_to_revive (callback: CallbackQuery):
	teams = get_all_teams ()
	team_names = [t[0] for t in teams]

	text = "💚 ВОСКРЕСИТЬ ИГРОКА\n\nВыберите команду:"

	await callback.message.edit_text (
		text,
		reply_markup = get_team_selection_keyboard (team_names)
	)


@router.callback_query (F.data.startswith ("select_team_"), lambda c: c.message.text.startswith ("💚"))
async def guard_select_player_to_revive (callback: CallbackQuery, state: FSMContext):
	team_name = callback.data.replace ("select_team_", "")
	await state.update_data (selected_team = team_name, action = "revive")

	text = f"💚 Команда: {team_name}\n\nВыберите игрока:"

	await callback.message.edit_text (
		text,
		reply_markup = get_player_list_keyboard (team_name, dead_only = True)
	)


# ===== АДМИН - ИГРОКИ =====
@router.callback_query (F.data == "admin_players")
async def admin_show_all_players (callback: CallbackQuery):
	teams = get_all_teams ()

	text = "👥 ВСЕ КОМАНДЫ\n\n"

	for team_name, exp, points in teams:
		members = get_team_members (team_name)

		text += f"{team_name} (🏆 {points} | 💎 {exp})\n"

		alive_count = sum (1 for m in members if m[5])
		text += f"Живых: {alive_count}/{len (members)}\n"

		for uid, fname, lname, prole, lvl, alive in members:
			status = "✅" if alive else "💀"
			role_emoji = ROLES[prole]["emoji"] if prole else "❓"
			text += f"  {status} {role_emoji} {fname} {lname}\n"

		text += "\n"

	keyboard = InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "◀️ Назад", callback_data = "back_to_menu")]
	])

	await callback.message.edit_text (text, reply_markup = keyboard)


# ===== НАЗАД В МЕНЮ =====
@router.callback_query (F.data == "back_to_menu")
async def back_to_main_menu (callback: CallbackQuery, state: FSMContext):
	await state.clear ()

	user_data = get_user_data (callback.from_user.id)
	role = user_data[1]

	if role == "player":
		team_name = user_data[2]
		members = get_team_members (team_name)

		text = f"🎮 Команда: {team_name}\n\nСостав:\n"
		for uid, fname, lname, prole, lvl, alive in members:
			if prole:
				role_data = ROLES[prole]
				status = "✅" if alive else "💀"
				text += f"{status} {role_data['emoji']} {fname} {lname} (Ур.{lvl})\n"

		await callback.message.edit_text (
			text,
			reply_markup = get_main_menu_keyboard (callback.from_user.id)
		)

	elif role == "operator":
		team_name = get_assigned_team (callback.from_user.id)
		text = f"👨‍💼 Оператор команды: {team_name}"

		await callback.message.edit_text (
			text,
			reply_markup = get_main_menu_keyboard (callback.from_user.id)
		)

	else:
		await callback.message.edit_text (
			"🎮 Игра идёт!",
			reply_markup = get_main_menu_keyboard (callback.from_user.id)
		)


# ===== АДМИН - УДАЛЕНИЕ КОМАНД =====
@router.callback_query (F.data == "admin_delete_teams")
async def admin_delete_teams (callback: CallbackQuery):
	teams = get_all_teams ()

	if not teams:
		await callback.answer ("Нет команд для удаления")
		return

	text = "🗑️ УДАЛЕНИЕ КОМАНДЫ\n\nВыберите команду для удаления:"

	keyboard = []
	for team_name, exp, points in teams:
		members = get_team_members (team_name)
		keyboard.append ([
			InlineKeyboardButton (
				text = f"{team_name} ({len (members)} игроков)",
				callback_data = f"admin_delete_team_{team_name}"
			)
		])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "start_game")])

	await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))


@router.callback_query (F.data.startswith ("admin_delete_team_"))
async def admin_confirm_delete_team (callback: CallbackQuery):
	team_name = callback.data.replace ("admin_delete_team_", "")

	delete_team (team_name)

	await callback.answer (f"✅ Команда {team_name} удалена!")

	# Возвращаемся к списку команд
	teams = get_all_teams ()

	if teams:
		text = "🗑️ УДАЛЕНИЕ КОМАНДЫ\n\nВыберите команду для удаления:"

		keyboard = []
		for t_name, exp, points in teams:
			members = get_team_members (t_name)
			keyboard.append ([
				InlineKeyboardButton (
					text = f"{t_name} ({len (members)} игроков)",
					callback_data = f"admin_delete_team_{t_name}"
				)
			])

		keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "start_game")])

		await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))
	else:
		await callback.message.edit_text (
			"✅ Все команды удалены!",
			reply_markup = InlineKeyboardMarkup (inline_keyboard = [
				[InlineKeyboardButton (text = "◀️ Назад", callback_data = "start_game")]
			])
		)


# ===== АДМИН - УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ =====
@router.callback_query (F.data == "admin_delete_users")
async def admin_delete_users (callback: CallbackQuery):
	staff = get_all_staff ()

	if not staff:
		await callback.answer ("Нет пользователей для удаления")
		return

	text = "👤 УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ\n\nВыберите пользователя для удаления:"

	role_names = {
		"operator": "Оператор",
		"guide": "Гид",
		"guard": "Охрана",
		"super_guard": "Супер Охрана",
		"admin": "Админ"
	}

	keyboard = []
	for user_id, role, first_name in staff:
		role_display = role_names.get (role, role)
		name_display = first_name if first_name else f"ID: {user_id}"
		keyboard.append ([
			InlineKeyboardButton (
				text = f"{name_display} ({role_display})",
				callback_data = f"admin_delete_user_{user_id}"
			)
		])

	keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "start_game")])

	await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))


@router.callback_query (F.data.startswith ("admin_delete_user_"))
async def admin_confirm_delete_user (callback: CallbackQuery):
	user_id_to_delete = int (callback.data.replace ("admin_delete_user_", ""))

	# Нельзя удалить себя
	if user_id_to_delete == callback.from_user.id:
		await callback.answer ("❌ Нельзя удалить себя!", show_alert = True)
		return

	# Получаем информацию о пользователе перед удалением
	user_data = get_user_data (user_id_to_delete)
	if user_data:
		user_name = user_data[3] if user_data[3] else f"ID: {user_id_to_delete}"
	else:
		user_name = f"ID: {user_id_to_delete}"

	delete_user (user_id_to_delete)

	await callback.answer (f"✅ Пользователь {user_name} удалён!")

	# Возвращаемся к списку пользователей
	staff = get_all_staff ()

	if staff:
		text = "👤 УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ\n\nВыберите пользователя для удаления:"

		role_names = {
			"operator": "Оператор",
			"guide": "Гид",
			"guard": "Охрана",
			"super_guard": "Супер Охрана",
			"admin": "Админ"
		}

		keyboard = []
		for uid, role, first_name in staff:
			role_display = role_names.get (role, role)
			name_display = first_name if first_name else f"ID: {uid}"
			keyboard.append ([
				InlineKeyboardButton (
					text = f"{name_display} ({role_display})",
					callback_data = f"admin_delete_user_{uid}"
				)
			])

		keyboard.append ([InlineKeyboardButton (text = "◀️ Назад", callback_data = "start_game")])

		await callback.message.edit_text (text, reply_markup = InlineKeyboardMarkup (inline_keyboard = keyboard))
	else:
		await callback.message.edit_text (
			"✅ Все пользователи удалены!",
			reply_markup = InlineKeyboardMarkup (inline_keyboard = [
				[InlineKeyboardButton (text = "◀️ Назад", callback_data = "start_game")]
			])
		)


# ===== АДМИН - ОТМЕНА ПОДГОТОВКИ =====
@router.callback_query (F.data == "admin_cancel_prep")
async def admin_cancel_prep (callback: CallbackQuery):
	reset_game_to_registration ()

	await callback.answer ("✅ Подготовка отменена!")
	await callback.message.edit_text (
		"✅ Подготовка отменена!\n\nИгра возвращена на этап регистрации.",
		reply_markup = InlineKeyboardMarkup (inline_keyboard = [
			[InlineKeyboardButton (text = "◀️ К статусу", callback_data = "start_game")]
		])
	)

	# Уведомляем всех
	conn = db.get_connection ()
	cursor = conn.cursor ()
	cursor.execute ("SELECT user_id FROM users WHERE role IN ('player', 'operator')")
	users = cursor.fetchall ()
	conn.close ()

	for user in users:
		try:
			await bot.send_message (
				user[0],
				"⚠️ Подготовка отменена!\n\nИгра возвращена на этап регистрации.\nНажмите /start для продолжения."
			)
		except:
			pass


# ===== АДМИН - ОСТАНОВКА ИГРЫ =====
@router.callback_query (F.data == "admin_stop_game")
async def admin_stop_game (callback: CallbackQuery, state: FSMContext):
	text = "⚠️ ОСТАНОВКА ИГРЫ\n\n"
	text += "Вы уверены, что хотите остановить игру?\n\n"
	text += "Это действие сбросит весь прогресс команд.\n\n"
	text += "Для подтверждения напишите:\n**Я подтверждаю**"

	keyboard = InlineKeyboardMarkup (inline_keyboard = [
		[InlineKeyboardButton (text = "❌ Отмена", callback_data = "back_to_menu")]
	])

	await callback.message.edit_text (text, reply_markup = keyboard)
	await state.set_state (AdminStates.confirming_stop_game)


@router.message (AdminStates.confirming_stop_game)
async def admin_confirm_stop_game (message: Message, state: FSMContext):
	if message.text == "Я подтверждаю":
		reset_game_to_preparation ()

		await message.answer (
			"✅ Игра остановлена!\n\nИгра возвращена на этап подготовки.",
			reply_markup = get_start_keyboard (message.from_user.id)
		)

		await state.clear ()

		# Уведомляем всех
		conn = db.get_connection ()
		cursor = conn.cursor ()
		cursor.execute ("SELECT user_id FROM users WHERE role IN ('player', 'operator', 'guide', 'guard', 'super_guard')")
		users = cursor.fetchall ()
		conn.close ()

		for user in users:
			try:
				await bot.send_message (
					user[0],
					"⚠️ ИГРА ОСТАНОВЛЕНА!\n\nИгра возвращена на этап подготовки.\nНажмите /start для продолжения."
				)
			except:
				pass
	else:
		await message.answer (
			"❌ Неверное подтверждение.\n\nДля остановки игры напишите точно:\n**Я подтверждаю**\n\nИли нажмите кнопку отмены выше."
		)


# ===== ОБРАБОТЧИК НЕАКТИВНЫХ КНОПОК =====
@router.callback_query (F.data == "noop")
async def noop_handler (callback: CallbackQuery):
	await callback.answer ()


# ===== ЗАПУСК БОТА =====
async def main ():
	dp.include_router (router)
	await dp.start_polling (bot)


if __name__ == "__main__":
	asyncio.run (main ())