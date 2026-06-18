"""BabyCare SQLite 数据库 - Render 部署用"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'babycare.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feeding (
            id TEXT PRIMARY KEY,
            baby_id TEXT NOT NULL,
            family_id TEXT DEFAULT '',
            feed_type TEXT NOT NULL DEFAULT 'left',
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT '',
            duration_minutes INTEGER DEFAULT 0,
            amount_ml INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            recorded_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sleep (
            id TEXT PRIMARY KEY,
            baby_id TEXT NOT NULL,
            family_id TEXT DEFAULT '',
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT '',
            duration_minutes INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            recorded_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS diaper (
            id TEXT PRIMARY KEY,
            baby_id TEXT NOT NULL,
            family_id TEXT DEFAULT '',
            diaper_type TEXT NOT NULL DEFAULT 'wet',
            time TEXT NOT NULL,
            note TEXT DEFAULT '',
            recorded_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS growth (
            id TEXT PRIMARY KEY,
            baby_id TEXT NOT NULL,
            family_id TEXT DEFAULT '',
            record_date TEXT NOT NULL,
            height_cm REAL,
            weight_kg REAL,
            head_circumference_cm REAL,
            note TEXT DEFAULT '',
            recorded_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vaccination (
            id TEXT PRIMARY KEY,
            baby_id TEXT NOT NULL,
            family_id TEXT DEFAULT '',
            vaccine_name TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            status TEXT DEFAULT 'upcoming',
            actual_date TEXT DEFAULT '',
            note TEXT DEFAULT '',
            recorded_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medication (
            id TEXT PRIMARY KEY,
            baby_id TEXT NOT NULL,
            family_id TEXT DEFAULT '',
            medicine_name TEXT NOT NULL,
            dosage TEXT DEFAULT '',
            unit TEXT DEFAULT '',
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT '',
            frequency TEXT DEFAULT '',
            note TEXT DEFAULT '',
            recorded_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# 模块加载时初始化
init_db()
