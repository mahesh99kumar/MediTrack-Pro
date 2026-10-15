import os
import sys
import shutil
import hashlib
import sqlite3
import subprocess
from datetime import datetime, timedelta

# Auto-install PyMySQL if missing
try:
    import pymysql
    import pymysql.cursors
except ImportError:
    print("Installing pymysql for phpMyAdmin connection...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql", "cryptography"])
        import pymysql
        import pymysql.cursors
    except Exception as e:
        print(f"Warning: pymysql install failed: {e}")

try:
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    def generate_password_hash(password):
        return 'sha256$' + hashlib.sha256(password.encode()).hexdigest()
    def check_password_hash(p_hash, password):
        if p_hash.startswith('sha256$'):
            return p_hash == 'sha256$' + hashlib.sha256(password.encode()).hexdigest()
        return False

from config import Config

class MySQLCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        # Convert SQLite style ? placeholders to MySQL %s
        if params is not None:
            formatted_query = query.replace('?', '%s')
            return self._cursor.execute(formatted_query, params)
        return self._cursor.execute(query)

    def executemany(self, query, params_list):
        formatted_query = query.replace('?', '%s')
        return self._cursor.executemany(formatted_query, params_list)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

class MySQLConnectionWrapper:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return MySQLCursorWrapper(self._conn.cursor(pymysql.cursors.DictCursor))

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

def get_db_connection():
    # Try MySQL first if configured
    if getattr(Config, 'DB_TYPE', 'mysql') == 'mysql':
        try:
            raw_conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                charset='utf8mb4',
                autocommit=False
            )
            return MySQLConnectionWrapper(raw_conn)
        except Exception as e:
            print(f"[Notice] MySQL connection error: {e}. Falling back to SQLite.")

    # SQLite Fallback
    conn = sqlite3.connect(getattr(Config, 'SQLITE_PATH', getattr(Config, 'DATABASE_PATH', 'pharmacy.db')))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            role VARCHAR(20) DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Medicines Table (Check if columns exist or create)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(150) NOT NULL,
            category VARCHAR(50) NOT NULL,
            batch_no VARCHAR(50) NOT NULL,
            expiry_date DATE NOT NULL,
            buy_price DECIMAL(10,2) NOT NULL,
            sell_price DECIMAL(10,2) NOT NULL,
            quantity INTEGER NOT NULL,
            min_stock INTEGER DEFAULT 10,
            supplier VARCHAR(100) DEFAULT 'Generic Pharma',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Customers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20) UNIQUE,
            email VARCHAR(100),
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            invoice_no VARCHAR(50) UNIQUE NOT NULL,
            customer_id INTEGER,
            customer_name VARCHAR(100) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            discount DECIMAL(10,2) DEFAULT 0,
            tax DECIMAL(10,2) DEFAULT 0,
            total_amount DECIMAL(10,2) NOT NULL,
            payment_mode VARCHAR(30) DEFAULT 'Cash',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Sale Items Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            sale_id INTEGER NOT NULL,
            medicine_id INTEGER NOT NULL,
            medicine_name VARCHAR(150) NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            total_price DECIMAL(10,2) NOT NULL
        )
    ''')

    conn.commit()

    # Seed Admin User if not exists
    cursor.execute('SELECT COUNT(*) as count FROM users')
    row = cursor.fetchone()
    if row['count'] == 0:
        admin_pass = generate_password_hash('Jaat$1628')
        cursor.execute('''
            INSERT INTO users (username, password, full_name, role)
            VALUES (?, ?, ?, ?)
        ''', ('maheshkakar99', admin_pass, 'Mahesh Kakar', 'admin'))
        conn.commit()

    # Seed Sample Medicines if table has 0 rows
    cursor.execute('SELECT COUNT(*) as count FROM medicines')
    row = cursor.fetchone()
    if row['count'] == 0:
        today = datetime.now()
        exp_soon = (today + timedelta(days=15)).strftime('%Y-%m-%d')
        exp_valid = (today + timedelta(days=365)).strftime('%Y-%m-%d')
        exp_long = (today + timedelta(days=730)).strftime('%Y-%m-%d')
        expired = (today - timedelta(days=10)).strftime('%Y-%m-%d')

        sample_medicines = [
            ('Paracetamol 650mg', 'Tablet', 'PCM-8841', exp_valid, 15.0, 30.0, 120, 20, 'Cipla Ltd.'),
            ('Amoxicillin 500mg', 'Capsule', 'AMX-2019', exp_valid, 45.0, 75.0, 60, 15, 'Sun Pharma'),
            ('Cetirizine 10mg', 'Tablet', 'CET-5512', exp_soon, 10.0, 25.0, 8, 20, 'Dr. Reddy'),
            ('Azithromycin 500mg', 'Tablet', 'AZI-9921', exp_long, 70.0, 120.0, 45, 10, 'Lupin Pharma'),
            ('Metformin 500mg', 'Tablet', 'MET-3301', exp_valid, 20.0, 42.0, 95, 25, 'Torrent Pharma'),
            ('Pantoprazole 40mg', 'Tablet', 'PAN-4412', exp_valid, 35.0, 65.0, 80, 20, 'Alkem Labs'),
            ('Benadryl Cough Syrup 100ml', 'Syrup', 'BND-1104', exp_valid, 65.0, 115.0, 35, 10, 'Johnson & Johnson')
        ]

        cursor.executemany('''
            INSERT INTO medicines (name, category, batch_no, expiry_date, buy_price, sell_price, quantity, min_stock, supplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_medicines)
        conn.commit()

    # Seed Sample Customers if empty
    cursor.execute('SELECT COUNT(*) as count FROM customers')
    row = cursor.fetchone()
    if row['count'] == 0:
        sample_customers = [
            ('Rahul Sharma', '9876543210', 'rahul.s@example.com', 'A-42 Sector 15, Rohini'),
            ('Walk-in Customer', '9999999999', 'walkin@store.com', 'Over the counter')
        ]
        cursor.executemany('''
            INSERT INTO customers (name, phone, email, address)
            VALUES (?, ?, ?, ?)
        ''', sample_customers)
        conn.commit()

    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
