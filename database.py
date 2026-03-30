import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


class CompatCursor:
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
    """Makes psycopg2 behave like sqlite3: converts ? to %s, uses RealDictCursor."""

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
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return CompatConnection(conn)


def _run_migration(c, raw, sql):
    """Run a single migration SQL, rolling back on error (e.g. column already exists)."""
    try:
        c.execute(sql)
        raw.commit()
    except Exception as e:
        raw.rollback()


def init_db():
    raw = psycopg2.connect(DATABASE_URL)
    c = raw.cursor()

    # ââ users ââââââââââââââââââââââââââââââââââââââââââââââââ
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT,
            creci TEXT,
            phone TEXT,
            plan TEXT DEFAULT 'free',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)
    raw.commit()
    for sql in [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS active INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS creci TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'free'",
    ]:
        _run_migration(c, raw, sql)

    # ââ inspections ââââââââââââââââââââââââââââââââââââââââââ
    c.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            type TEXT,
            status TEXT DEFAULT 'rascunho',
            property_address TEXT,
            property_type TEXT,
            property_area TEXT,
            inspection_date TEXT,
            bairro TEXT,
            complemento TEXT,
            cep TEXT,
            cidade TEXT,
            estado TEXT,
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
            corretor_name TEXT,
            corretor_creci TEXT,
            corretor_phone TEXT,
            corretor_email TEXT,
            imobiliaria_name TEXT,
            imobiliaria_cnpj TEXT,
            imobiliaria_phone TEXT,
            imobiliaria_address TEXT,
            observations TEXT,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')),
            updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)
    raw.commit()
    for sql in [
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS type TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS property_address TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS property_type TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS property_area TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS inspection_date TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS bairro TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS complemento TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS cep TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS cidade TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS estado TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS corretor_name TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS corretor_creci TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS corretor_phone TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS corretor_email TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_name TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_cnpj TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_phone TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_address TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS observations TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS locadores_json TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS locatarios_json TEXT",
    ]:
        _run_migration(c, raw, sql)

    # ââ rooms ââââââââââââââââââââââââââââââââââââââââââââââââ
    c.execute("""
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS ambientes_json TEXT",
        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            inspection_id TEXT NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            order_num INTEGER DEFAULT 0,
            general_condition TEXT,
            observations TEXT,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)
    raw.commit()
    for sql in [
        "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS general_condition TEXT",
        "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS observations TEXT",
    ]:
        _run_migration(c, raw, sql)

    # ââ room_items âââââââââââââââââââââââââââââââââââââââââââ
    c.execute("""
        CREATE TABLE IF NOT EXISTS room_items (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            condition TEXT,
            ai_description TEXT,
            manual_description TEXT,
            photo_path TEXT,
            photo_filename TEXT,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)
    raw.commit()
    for sql in [
        "ALTER TABLE room_items ADD COLUMN IF NOT EXISTS ai_description TEXT",
        "ALTER TABLE room_items ADD COLUMN IF NOT EXISTS manual_description TEXT",
        "ALTER TABLE room_items ADD COLUMN IF NOT EXISTS photo_path TEXT",
        "ALTER TABLE room_items ADD COLUMN IF NOT EXISTS photo_filename TEXT",
    ]:
        _run_migration(c, raw, sql)

    # ââ item_photos ââââââââââââââââââââââââââââââââââââââââââ
    c.execute("""
        CREATE TABLE IF NOT EXISTS item_photos (
            id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL REFERENCES room_items(id) ON DELETE CASCADE,
            filename TEXT,
            data BYTEA,
            created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
        )
    """)
    raw.commit()

    # ââ signatures âââââââââââââââââââââââââââââââââââââââââââ
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

    # -- password_reset_tokens ------------------------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    raw.commit()


    # -- admin: users extra columns ------------------------------------------
    for _sql in [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_reason TEXT",
    ]:
        try:
            c.execute(_sql)
            raw.commit()
        except Exception:
            raw.rollback()

    # -- admin: plans ---------------------------------------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            monthly_price REAL DEFAULT 0,
            usage_limit INTEGER,
            price_per_photo REAL DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    raw.commit()

    # -- admin: user_plans ----------------------------------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_plans (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            assigned_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id)
        )
    """)
    raw.commit()

    # -- admin: usage_logs ----------------------------------------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS usage_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    raw.commit()
    raw.close()
    print("✅ Banco de dados PostgreSQL inicializado com sucesso")
