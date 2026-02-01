#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных дней рождения.
Использует SQLite для хранения информации о людях.
"""

import sqlite3
import os
from datetime import datetime, date
from typing import List, Tuple, Optional


class BirthdayDatabase:
    """Класс для работы с базой данных дней рождения."""
    
    def __init__(self, db_path: str = "birthdays.db"):
        """Инициализация базы данных."""
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Получить соединение с базой данных."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализировать таблицу базы данных."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                birthday_date DATE NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создаем индекс для быстрого поиска по user_id
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id ON birthdays(user_id)
        """)
        
        conn.commit()
        conn.close()
    
    def add_person(self, name: str, birthday_date: date, user_id: int) -> bool:
        """Добавить человека в базу данных."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO birthdays (name, birthday_date, user_id)
                VALUES (?, ?, ?)
            """, (name, birthday_date.isoformat(), user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении: {e}")
            return False
    
    def get_all_people(self, user_id: Optional[int] = None) -> List[dict]:
        """Получить всех людей из базы данных."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("SELECT * FROM birthdays WHERE user_id = ? ORDER BY name", (user_id,))
        else:
            cursor.execute("SELECT * FROM birthdays ORDER BY name")
        
        rows = cursor.fetchall()
        
        people = []
        today = date.today()
        
        for row in rows:
            birthday_date = datetime.strptime(row['birthday_date'], '%Y-%m-%d').date()
            age = self.calculate_age(birthday_date, today)
            days_until = self.days_until_birthday(birthday_date, today)
            
            people.append({
                'id': row['id'],
                'name': row['name'],
                'birthday_date': birthday_date,
                'user_id': row['user_id'],
                'age': age,
                'days_until': days_until
            })
        
        conn.close()
        return people
    
    def delete_person(self, person_id: int) -> bool:
        """Удалить человека из базы данных."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM birthdays WHERE id = ?", (person_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при удалении: {e}")
            return False
    
    def get_people_with_birthday_in_days(self, days: int) -> List[dict]:
        """Получить людей, у которых день рождения через указанное количество дней."""
        people = self.get_all_people()
        result = []
        
        for person in people:
            if person['days_until'] == days:
                result.append(person)
        
        return result
    
    def get_user_ids_with_birthdays_today(self) -> List[int]:
        """Получить список уникальных user_id, у которых есть люди с днем рождения сегодня."""
        people = self.get_people_with_birthday_in_days(0)
        return list(set([p['user_id'] for p in people]))
    
    @staticmethod
    def calculate_age(birthday: date, today: date) -> int:
        """Вычислить текущий возраст человека."""
        age = today.year - birthday.year
        if (today.month, today.day) < (birthday.month, birthday.day):
            age -= 1
        return age
    
    @staticmethod
    def days_until_birthday(birthday: date, today: date) -> int:
        """Вычислить количество дней до следующего дня рождения."""
        # Следующий день рождения в этом году
        next_birthday = date(today.year, birthday.month, birthday.day)
        
        # Если день рождения уже прошел в этом году, берем следующий год
        if next_birthday < today:
            next_birthday = date(today.year + 1, birthday.month, birthday.day)
        
        # Если сегодня день рождения, возвращаем 0
        if next_birthday == today:
            return 0
        
        return (next_birthday - today).days
