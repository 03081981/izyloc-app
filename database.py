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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_cents INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS cpf VARCHAR(14)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
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
            corretor_cpf TEXT,
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
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS corretor_cpf TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_name TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_cnpj TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_phone TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_address TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS observations TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS locadores_json TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS locatarios_json TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS ambientes_json TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS imobiliaria_email TEXT",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS responsavel TEXT DEFAULT 'proprietario'",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS autentique_doc_id VARCHAR(100)",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS autentique_status VARCHAR(30) DEFAULT 'pending'",
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS autentique_sent_at TIMESTAMPTZ",
        # Normaliza status antigos do Autentique (eram em ingles; agora em PT
        # pra casar com _mlStatusKey do frontend)
        "UPDATE inspections SET status='aguardando_assinatura' WHERE status='awaiting_signature'",
        "UPDATE inspections SET status='assinado_digital' WHERE status='signed'",
    ]:
        _run_migration(c, raw, sql)

    # ââ rooms ââââââââââââââââââââââââââââââââââââââââââââââââ
    c.execute("""
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

    c.execute("""CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_email_verif_token ON email_verification_tokens(token)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_email_verif_user ON email_verification_tokens(user_id)")
    raw.commit()

    c.execute("""CREATE TABLE IF NOT EXISTS email_queue (
            id SERIAL PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            to_email VARCHAR(255) NOT NULL,
            template VARCHAR(50) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            body_html TEXT NOT NULL,
            body_text TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            provider VARCHAR(20),
            provider_id VARCHAR(100),
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            last_error TEXT,
            next_retry_at TIMESTAMP,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status, next_retry_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_email_queue_user ON email_queue(user_id)")
    raw.commit()

    c.execute("""CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(100) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            ip VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            last_used_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
    raw.commit()

    c.execute("""CREATE TABLE IF NOT EXISTS balance_transactions (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(20) NOT NULL,
            amount_cents INTEGER NOT NULL,
            balance_after_cents INTEGER NOT NULL,
            description TEXT,
            inspection_id TEXT,
            room_id TEXT,
            payment_id VARCHAR(100),
            analysis_type VARCHAR(20),
            photos_count INTEGER,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_balance_trans_user ON balance_transactions(user_id, created_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_balance_trans_type ON balance_transactions(type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_balance_trans_payment ON balance_transactions(payment_id)")
    raw.commit()

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL,
            value_type VARCHAR(20) NOT NULL DEFAULT 'string',
            category VARCHAR(50),
            description TEXT,
            updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    raw.commit()

    for _s_row in [
        ('price_per_photo_convencional_cents', '50', 'integer', 'pricing', 'Preço por foto da análise Convencional em centavos (R$ 0,50)'),
        ('price_per_photo_premium_cents', '90', 'integer', 'pricing', 'Preço por foto da análise Premium em centavos (R$ 0,90)'),
        ('welcome_bonus_cents', '500', 'integer', 'pricing', 'Bônus de boas-vindas em centavos após verificação de email (R$ 5,00)'),
        ('min_photos_per_room', '10', 'integer', 'general', 'Quantidade mínima de fotos necessárias por ambiente para análise'),
    ]:
        c.execute("INSERT INTO settings (key, value, value_type, category, description) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING", _s_row)
    raw.commit()

    # user_profile_config: perfil de conta (imobiliaria | corretor | proprietario)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_profile_config (
            id VARCHAR(64) PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL UNIQUE,
            tipo_perfil VARCHAR(20) NOT NULL DEFAULT 'imobiliaria',
            nome VARCHAR(200),
            cpf VARCHAR(20),
            creci VARCHAR(50),
            telefone VARCHAR(30),
            email_contato VARCHAR(200),
            nome_imobiliaria VARCHAR(200),
            cnpj VARCHAR(20),
            creci_imobiliaria VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    raw.commit()
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_profile_config_user ON user_profile_config(user_id)")
    raw.commit()

    # corretores: cadastro da equipe da imobiliaria
    c.execute("""
        CREATE TABLE IF NOT EXISTS corretores (
            id VARCHAR(64) PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            nome VARCHAR(200) NOT NULL,
            creci VARCHAR(50),
            cpf VARCHAR(20),
            ativo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    raw.commit()
    c.execute("CREATE INDEX IF NOT EXISTS idx_corretores_user ON corretores(user_id)")
    raw.commit()

    # Migration: adicionar coluna email (idempotente)
    _run_migration(c, raw, "ALTER TABLE corretores ADD COLUMN IF NOT EXISTS email VARCHAR(200)")

    # Task #167: tabela anti-abuso do bônus de boas-vindas. Persistente:
    # NÃO tem FK para users (deve sobreviver a delete de conta). Email
    # UNIQUE bloqueia recadastro do mesmo endereço para receber o bônus
    # novamente. Sempre normalizado em lowercase no INSERT.
    c.execute("""
        CREATE TABLE IF NOT EXISTS bonus_concedido (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            bonus_cents INTEGER NOT NULL,
            granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_id_origem TEXT,
            notes TEXT
        )
    """)
    raw.commit()
    c.execute("CREATE INDEX IF NOT EXISTS idx_bonus_concedido_email ON bonus_concedido(email)")
    raw.commit()

    raw.close()
    print("✅ Banco de dados PostgreSQL inicializado com sucesso")
