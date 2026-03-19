import sqlite3
import os
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'izylo.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        company_name TEXT,
        creci TEXT,
        phone TEXT,
        plan TEXT DEFAULT 'basic',
        inspections_used INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS inspections (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('entrada','saida')),
        status TEXT DEFAULT 'rascunho',
        property_address TEXT,
        property_type TEXT,
        property_area TEXT,
        inspection_date TEXT,
        -- Locador
        locador_name TEXT,
        locador_cpf TEXT,
        locador_rg TEXT,
        locador_phone TEXT,
        locador_email TEXT,
        -- Locatario
        locatario_name TEXT,
        locatario_cpf TEXT,
        locatario_rg TEXT,
        locatario_phone TEXT,
        locatario_email TEXT,
        -- Múltiplos locadores/locatários (JSON arrays)
        locadores_json TEXT,
        locatarios_json TEXT,
        -- Corretor / Avaliador
        corretor_name TEXT,
        corretor_creci TEXT,
        corretor_phone TEXT,
        corretor_email TEXT,
        -- Imobiliaria
        imobiliaria_name TEXT,
        imobiliaria_cnpj TEXT,
        imobiliaria_phone TEXT,
        imobiliaria_address TEXT,
        -- Geral
        observations TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS rooms (
        id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        name TEXT NOT NULL,
        order_num INTEGER DEFAULT 0,
        general_condition TEXT,
        observations TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(inspection_id) REFERENCES inspections(id)
    );

    CREATE TABLE IF NOT EXISTS room_items (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        name TEXT NOT NULL,
        condition TEXT,
        ai_description TEXT,
        manual_description TEXT,
        photo_path TEXT,
        photo_filename TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(room_id) REFERENCES rooms(id)
    );

    CREATE TABLE IF NOT EXISTS item_photos (
        id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL,
        photo_path TEXT NOT NULL,
        photo_filename TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(item_id) REFERENCES room_items(id)
    );

    CREATE TABLE IF NOT EXISTS signatures (
        id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        party_type TEXT NOT NULL,
        party_name TEXT,
        signature_data TEXT,
        signed_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(inspection_id) REFERENCES inspections(id)
    );
    """)
    conn.commit()

    # Migration: add JSON columns if they don't exist yet
    try:
        conn.execute("ALTER TABLE inspections ADD COLUMN locadores_json TEXT")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE inspections ADD COLUMN locatarios_json TEXT")
        conn.commit()
    except Exception:
        pass

    conn.close()
    print("✅ Banco de dados inicializado")

if __name__ == '__main__':
    init_db()
