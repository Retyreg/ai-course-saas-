from supabase import create_client
import streamlit as st
import hashlib
import os

# --- Инициализация Supabase ---
def get_supabase():
    try:
        # Пробуем из streamlit secrets
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except:
        # Или из переменных окружения
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL и SUPABASE_KEY не найдены!")
    
    return create_client(url, key)

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Функции для кредитов ---
def get_user_credits(email):
    """Получить баланс кредитов"""
    try:
        supabase = get_supabase()
        result = supabase.table("users_credits").select("credits").eq("email", email).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]["credits"]
        return 0
    except Exception as e:
        print(f"Error getting credits: {e}")
        return 0

def deduct_credit(email, amount=1):
    """Списать кредиты"""
    try:
        supabase = get_supabase()
        current = get_user_credits(email)
        if current >= amount:
            supabase.table("users_credits").update({"credits": current - amount}).eq("email", email).execute()
            return True
        return False
    except Exception as e:
        print(f"Error deducting credits: {e}")
        return False

def add_credits(email, amount):
    """Добавить кредиты (для админки)"""
    try:
        supabase = get_supabase()
        # Проверяем существует ли пользователь
        result = supabase.table("users_credits").select("credits").eq("email", email).execute()
        
        if result.data and len(result.data) > 0:
            # Обновляем
            new_balance = result.data[0]["credits"] + amount
            supabase.table("users_credits").update({"credits": new_balance}).eq("email", email).execute()
        else:
            # Создаём нового
            supabase.table("users_credits").insert({"email": email, "credits": amount}).execute()
        return True
    except Exception as e:
        print(f"Error adding credits: {e}")
        return False

# --- Авторизация (для web-app) ---
def login_user(email, password):
    try:
        supabase = get_supabase()
        # Простая проверка по хэшу (можно улучшить через Supabase Auth)
        result = supabase.table("users_auth").select("*").eq("email", email).eq("password_hash", hash_pass(password)).execute()
        return len(result.data) > 0
    except:
        return False

def register_user(email, password):
    try:
        supabase = get_supabase()
        # Создаём запись авторизации
        supabase.table("users_auth").insert({"email": email, "password_hash": hash_pass(password)}).execute()
        # Даём начальные кредиты
        supabase.table("users_credits").insert({"email": email, "credits": 5}).execute()
        return True
    except:
        return False

# --- Mock для совместимости со старым кодом ---
class MockSupabaseClient:
    def table(self, name):
        return self
    def select(self, *args):
        return self
    def eq(self, col, val):
        return self
    def update(self, data):
        return self
    def execute(self):
        return type('obj', (object,), {'data': []})()

supabase = get_supabase() if os.environ.get("SUPABASE_URL") else MockSupabaseClient()
