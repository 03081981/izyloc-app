import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Fix Railway's postgres:// scheme to postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


class CompatCursor:
    """Wraps a psycopg2 RealDictCursor to behave like sqlite3's cursor."""
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return None

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __iter__(self):
        return iter(self._cursor.fetchall())


class CompatConnection:
    """Thin wrapper making psycopg2 behave like sqlite3 for this codebase.

    Key behaviours:
    - Converts '?' placeholders to '%s' automatically
    - Uses RealDictCursor so rows support dict(row) and named-column access
    - Exposes .execute(), .commit(), .rollback(), .close()
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if params is not None:
            params = list(params) if not isinstance(params, (list, tuple)) else params
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return CompatCursor(cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False


def get_conn():
    """Return a CompatConnection wrapping a fresh psycopg2 connection."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return CompatConnection(conn)


def init_db():
    """Create all tables if they do not already exist."""
    raw = psycopg2.connect(DATABASE_URL)
    c = raw.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT,
            creci TEXT,
            phone TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            address TEXT,
            city TEXT,
            state TEXT,
            property_type TEXT,
            inspection_date TEXT,
            locador_name TEXT,
            locador_cpf TEXT,
            locador_rg TEXT,
            locador_phone TEXT,
            locador_email TEXT,
            locatario_name TEXT,
            locatario_cpf TEXT,
            locatario_rg TEXT,
            locatario_phone TEXT,
            locatario_email TEXT,
            locadores_json TEXT,
            locatarios_json TEXT,
            status TEXT DEFAULT 'em_andamento',
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            inspection_id TEXT NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            order_num INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS room_items (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            condition TEXT,
            notes TEXT,
            order_num INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS item_photos (
            id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL REFERENCES room_items(id) ON DELETE CASCADE,
            filename TEXT,
            data BYTEA,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS signatures (
            id TEXT PRIMARY KEY,
            inspection_id TEXT NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
            party TEXT,
            signature_data TEXT,
            signed_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)

    raw.commit()
    raw.close()
    print("\u2705 Banco de dados PostgreSQL inicializado com sucesso")
