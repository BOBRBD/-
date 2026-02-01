#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для напоминаний о днях рождения.
Отправляет уведомления за 24 часа до дня рождения.
"""

import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from database import BirthdayDatabase

# Загружаем переменные окружения
# Явно указываем путь к файлу .env в текущей директории
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения. Создайте файл .env и добавьте BOT_TOKEN=ваш_токен")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация базы данных
db = BirthdayDatabase()

# Хранилище активных пользователей (chat_id)
active_users = set()


# Состояния для FSM
class AddPersonStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()


# Функции для создания клавиатур
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Создать главную клавиатуру с основными функциями."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить человека", callback_data="add_person")],
        [InlineKeyboardButton(text="📋 Показать список", callback_data="show_list")],
        [InlineKeyboardButton(text="🗑️ Удалить человека", callback_data="delete_person")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    return keyboard


def get_delete_keyboard(people: list) -> InlineKeyboardMarkup:
    """Создать клавиатуру для выбора человека для удаления."""
    buttons = []
    for person in people:
        buttons.append([InlineKeyboardButton(
            text=f"🗑️ {person['name']} ({person['birthday_date'].strftime('%d.%m.%Y')})",
            callback_data=f"delete_{person['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    
    welcome_text = (
        "🎉 Добро пожаловать в бота напоминаний о днях рождения!\n\n"
        "Я помогу вам не забыть о важных днях рождения ваших близких.\n"
        "Бот автоматически напомнит вам за 24 часа до дня рождения.\n\n"
        "Выберите действие:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    user_id = message.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    
    help_text = (
        "📖 Справка по боту:\n\n"
        "🔹 <b>Добавить человека</b> - добавить нового человека в список с датой рождения\n"
        "🔹 <b>Показать список</b> - просмотреть всех людей с их возрастом и днями до дня рождения\n"
        "🔹 <b>Удалить человека</b> - удалить человека из списка\n\n"
        "⏰ Бот автоматически отправляет напоминания за 24 часа до дня рождения.\n\n"
        "Используйте кнопки ниже для навигации."
    )
    await message.answer(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")


# Обработчики callback-кнопок
@dp.callback_query(F.data == "add_person")
async def callback_add_person(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления человека."""
    user_id = callback.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    
    await callback.message.answer("👤 Введите имя человека:")
    await state.set_state(AddPersonStates.waiting_for_name)
    await callback.answer()


@dp.callback_query(F.data == "show_list")
async def callback_show_list(callback: CallbackQuery):
    """Показать список всех людей."""
    user_id = callback.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    people = db.get_all_people(user_id=user_id)
    
    if not people:
        await callback.message.answer(
            "📋 Список пуст. Добавьте первого человека, используя кнопку ниже.",
            reply_markup=get_main_keyboard()
        )
    else:
        list_text = "📋 <b>Список дней рождения:</b>\n\n"
        
        for person in people:
            age_text = f"{person['age']} лет"
            days_text = f"{person['days_until']} дн."
            
            if person['days_until'] == 0:
                days_text = "🎉 Сегодня!"
            elif person['days_until'] == 1:
                days_text = "🎂 Завтра!"
            
            list_text += (
                f"👤 <b>{person['name']}</b>\n"
                f"📅 {person['birthday_date'].strftime('%d.%m.%Y')}\n"
                f"🎂 Возраст: {age_text}\n"
                f"⏰ До дня рождения: {days_text}\n\n"
            )
        
        await callback.message.answer(list_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    
    await callback.answer()


@dp.callback_query(F.data == "delete_person")
async def callback_delete_person(callback: CallbackQuery):
    """Показать список для удаления."""
    user_id = callback.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    people = db.get_all_people(user_id=user_id)
    
    if not people:
        await callback.message.answer(
            "📋 Список пуст. Нечего удалять.",
            reply_markup=get_main_keyboard()
        )
    else:
        await callback.message.answer(
            "🗑️ Выберите человека для удаления:",
            reply_markup=get_delete_keyboard(people)
        )
    
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_"))
async def callback_confirm_delete(callback: CallbackQuery):
    """Удалить выбранного человека."""
    person_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    people = db.get_all_people(user_id=user_id)
    
    person = next((p for p in people if p['id'] == person_id), None)
    
    if person and db.delete_person(person_id):
        await callback.message.answer(
            f"✅ Человек <b>{person['name']}</b> успешно удален из списка.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "❌ Ошибка при удалении. Попробуйте снова.",
            reply_markup=get_main_keyboard()
        )
    
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery):
    """Отменить операцию."""
    await callback.message.answer(
        "❌ Операция отменена.",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Показать справку."""
    help_text = (
        "📖 <b>Справка по боту:</b>\n\n"
        "🔹 <b>Добавить человека</b> - добавить нового человека в список с датой рождения\n"
        "🔹 <b>Показать список</b> - просмотреть всех людей с их возрастом и днями до дня рождения\n"
        "🔹 <b>Удалить человека</b> - удалить человека из списка\n\n"
        "⏰ Бот автоматически отправляет напоминания за 24 часа до дня рождения.\n\n"
        "Используйте кнопки ниже для навигации."
    )
    await callback.message.answer(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    await callback.answer()


# Обработчики состояний для добавления человека
@dp.message(AddPersonStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработать введенное имя."""
    user_id = message.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    
    name = message.text.strip()
    
    if not name or len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите корректное имя:")
        return
    
    await state.update_data(name=name)
    await state.set_state(AddPersonStates.waiting_for_date)
    await message.answer(
        f"📅 Введите дату рождения для <b>{name}</b> в формате ДД.ММ.ГГГГ\n"
        f"Например: 15.03.1990",
        parse_mode="HTML"
    )


@dp.message(AddPersonStates.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Обработать введенную дату."""
    user_id = message.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    
    date_text = message.text.strip()
    data = await state.get_data()
    name = data.get('name')
    
    try:
        # Парсим дату в формате ДД.ММ.ГГГГ
        birthday_date = datetime.strptime(date_text, '%d.%m.%Y').date()
        
        # Проверяем, что дата не в будущем
        if birthday_date > date.today():
            await message.answer("❌ Дата рождения не может быть в будущем. Введите корректную дату:")
            return
        
        # Добавляем в базу данных
        user_id = message.from_user.id
        if db.add_person(name, birthday_date, user_id):
            age = db.calculate_age(birthday_date, date.today())
            days_until = db.days_until_birthday(birthday_date, date.today())
            
            await message.answer(
                f"✅ <b>{name}</b> успешно добавлен в список!\n\n"
                f"📅 Дата рождения: {birthday_date.strftime('%d.%m.%Y')}\n"
                f"🎂 Возраст: {age} лет\n"
                f"⏰ До дня рождения: {days_until} дней",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при добавлении. Попробуйте снова.",
                reply_markup=get_main_keyboard()
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ\n"
            "Например: 15.03.1990"
        )


# Функция для отправки напоминаний
async def send_birthday_reminders():
    """Отправлять напоминания о днях рождения за 24 часа."""
    while True:
        try:
            # Получаем людей, у которых день рождения через 24 часа
            people = db.get_people_with_birthday_in_days(1)
            
            if people:
                # Группируем по пользователям
                user_reminders = {}
                for person in people:
                    user_id = person['user_id']
                    if user_id not in user_reminders:
                        user_reminders[user_id] = []
                    user_reminders[user_id].append(person)
                
                # Отправляем напоминания каждому пользователю
                for user_id, persons in user_reminders.items():
                    if user_id in active_users:
                        for person in persons:
                            reminder_text = (
                                f"⏰ <b>Напоминание о дне рождения!</b>\n\n"
                                f"🎂 Завтра день рождения у <b>{person['name']}</b>!\n"
                                f"📅 Дата рождения: {person['birthday_date'].strftime('%d.%m.%Y')}\n"
                                f"🎉 Завтра ему/ей исполнится {person['age'] + 1} лет!\n\n"
                                f"Не забудьте поздравить! 🎁"
                            )
                            
                            try:
                                await bot.send_message(user_id, reminder_text, parse_mode="HTML")
                                logger.info(f"Напоминание отправлено пользователю {user_id} о {person['name']}")
                            except Exception as e:
                                logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
                                # Удаляем неактивного пользователя из списка
                                active_users.discard(user_id)
            
            # Проверяем каждые час (для более точных напоминаний)
            await asyncio.sleep(60 * 60)
            
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний: {e}")
            await asyncio.sleep(60)


# Обработчик всех остальных сообщений
@dp.message()
async def handle_other_messages(message: Message):
    """Обработчик всех остальных сообщений."""
    user_id = message.from_user.id
    active_users.add(user_id)  # Добавляем пользователя в список активных
    
    await message.answer(
        "👋 Используйте кнопки ниже для работы с ботом или команду /help для справки.",
        reply_markup=get_main_keyboard()
    )


async def main():
    """Основная функция для запуска бота."""
    logger.info("Запуск бота напоминаний о днях рождения...")
    
    # Удаляем вебхук и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем задачу для напоминаний в фоне
    asyncio.create_task(send_birthday_reminders())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
