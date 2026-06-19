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

    # 用户表：通过微信 openid 唯一标识
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid TEXT UNIQUE NOT NULL,
            nickname TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 家庭表：一个家庭 = 一个宝宝
    conn.execute("""
        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id TEXT UNIQUE NOT NULL,
            baby_name TEXT DEFAULT '宝宝',
            baby_birthday TEXT DEFAULT '',
            baby_avatar TEXT DEFAULT '',
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 家庭成员表：家庭与用户的关联
    conn.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id TEXT NOT NULL,
            openid TEXT NOT NULL,
            role TEXT DEFAULT 'other',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(family_id, openid)
        )
    """)

    # 索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_family_members_openid ON family_members(openid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_family_members_family_id ON family_members(family_id)")

    conn.commit()
    conn.close()

# 模块加载时初始化
init_db()
