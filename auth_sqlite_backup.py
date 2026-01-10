import sqlite3
import hashlib
import pandas as pd

# Имя локальной базы данных
DB_FILE = "users.db"

def init_db():
    """Создает таблицу пользователей, если её нет"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Создаем таблицу
    c.execute('''CREATE TABLE IF NOT EXISTS users_credits 
                 (email TEXT PRIMARY KEY, password TEXT, credits INTEGER)''')
    
    # Создаем АДМИНА по умолчанию (пароль: admin)
    admin_pass = hashlib.sha256('admin'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users_credits VALUES (?, ?, ?)", 
              ('vatyutovd@gmail.com', admin_pass, 1000))
    
    conn.commit()
    conn.close()

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- ФУНКЦИИ ДЛЯ APP.PY ---

def login_user(email, password):
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users_credits WHERE email=? AND password=?", (email, hash_pass(password)))
    user = c.fetchone()
    conn.close()
    return user is not None

def register_user(email, password):
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # При регистрации даем 5 бесплатных кредитов
        c.execute("INSERT INTO users_credits VALUES (?, ?, ?)", (email, hash_pass(password), 5)) 
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_user_credits(email):
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users_credits WHERE email=?", (email,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def deduct_credit(email):
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users_credits SET credits = credits - 1 WHERE email=?", (email,))
    conn.commit()
    conn.close()

# --- ЭМУЛЯЦИЯ SUPABASE ДЛЯ АДМИНКИ ---
# Чтобы код в app.py (auth.supabase...) не падал с ошибкой,
# мы делаем "фэйковый" класс, который работает с нашей SQLite.

class MockResponse:
    def __init__(self, data):
        self.data = data

class MockQuery:
    def __init__(self, table_name):
        self.table = table_name
        self.current_filter = None
    
    def select(self, *args):
        return self
    
    def eq(self, col, val):
        self.current_filter = (col, val)
        return self
    
    def update(self, data_dict):
        # Реальное обновление в SQLite для админки
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if self.current_filter:
            col, val = self.current_filter
            # Обновляем только кредиты (так как в админке обновляют их)
            if 'credits' in data_dict:
                c.execute(f"UPDATE {self.table} SET credits = ? WHERE {col} = ?", (data_dict['credits'], val))
        conn.commit()
        conn.close()
        return self

    def execute(self):
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(f"SELECT * FROM {self.table}", conn)
        conn.close()
        return MockResponse(df.to_dict('records'))

class MockSupabaseClient:
    def table(self, name):
        return MockQuery(name)

# Создаем объект, к которому обращается app.py
supabase = MockSupabaseClient()
