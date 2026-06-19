import os
import re
from contextlib import contextmanager
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.sql"
SCHEMA_PATH = BASE_DIR / "database.sql"

MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "123456"),
    "database": os.environ.get("MYSQL_DATABASE", "hospital"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": False,
}

_ready = False


def _normalize_sql(sql):
    return sql.replace("?", "%s")


def get_connection(use_database=True):
    config = dict(MYSQL_CONFIG)
    if not use_database:
        config.pop("database")
    return pymysql.connect(**config)


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _split_statements(sql_text):
    statements = []
    for part in sql_text.split(";"):
        stmt = part.strip()
        if not stmt or stmt.startswith("--"):
            continue
        stmt = re.sub(r"^\s*--.*$", "", stmt, flags=re.MULTILINE).strip()
        if stmt:
            statements.append(stmt)
    return statements


def _run_sql_file(path, conn):
    with open(path, encoding="utf-8") as f:
        statements = _split_statements(f.read())
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)


def init_db():
    if not CONFIG_PATH.exists() or not SCHEMA_PATH.exists():
        raise FileNotFoundError("config.sql or database.sql not found")

    conn = get_connection(use_database=False)
    try:
        _run_sql_file(CONFIG_PATH, conn)
        conn.commit()
    finally:
        conn.close()

    conn = get_connection()
    try:
        _run_sql_file(SCHEMA_PATH, conn)
        conn.commit()
    finally:
        conn.close()


def is_initialized():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'users'")
                return cur.fetchone() is not None
    except pymysql.Error:
        return False


def ensure_ready():
    global _ready
    if _ready:
        return
    try:
        if not is_initialized():
            init_db()
    except pymysql.OperationalError as exc:
        if exc.args[0] == 1049:
            init_db()
        else:
            raise
    _ready = True


def query_one(sql, params=()):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_normalize_sql(sql), params)
            return cur.fetchone()


def query_all(sql, params=()):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_normalize_sql(sql), params)
            return cur.fetchall()


def execute(sql, params=()):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_normalize_sql(sql), params)
            return cur.lastrowid


def execute_many(sql, params_list):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.executemany(_normalize_sql(sql), params_list)


def get_dashboard_stats():
    stats = query_one("""
        SELECT
            (SELECT COUNT(*) FROM patients) AS total_patients,
            (SELECT COUNT(*) FROM predictions) AS total_predictions,
            (SELECT COUNT(*) FROM predictions WHERE risk_level = 'High') AS high_risk_count,
            (SELECT COUNT(*) FROM predictions WHERE risk_level = 'Medium') AS medium_risk_count,
            (SELECT COUNT(*) FROM predictions WHERE risk_level = 'Low') AS low_risk_count,
            (SELECT ROUND(AVG(readmission_risk), 1) FROM predictions) AS avg_risk
    """)
    return stats or {
        "total_patients": 0,
        "total_predictions": 0,
        "high_risk_count": 0,
        "medium_risk_count": 0,
        "low_risk_count": 0,
        "avg_risk": 0,
    }


def get_recent_predictions(limit=10):
    return query_all("""
        SELECT p.*, pt.first_name, pt.last_name
        FROM predictions p
        LEFT JOIN patients pt ON p.patient_id = pt.patient_id
        ORDER BY p.created_at DESC
        LIMIT ?
    """, (limit,))


def get_monthly_predictions():
    return query_all("""
        SELECT
            DATE_FORMAT(created_at, '%%Y-%%m') AS month,
            COUNT(*) AS total,
            SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END) AS high_risk,
            ROUND(AVG(readmission_risk), 1) AS avg_risk
        FROM predictions
        GROUP BY DATE_FORMAT(created_at, '%%Y-%%m')
        ORDER BY month DESC
        LIMIT 12
    """)


def search_patients(search="", page=1, per_page=10):
    offset = (page - 1) * per_page
    params = []
    where = ""

    if search:
        where = """
            WHERE first_name LIKE ? OR last_name LIKE ?
            OR patient_id LIKE ? OR primary_diagnosis LIKE ?
        """
        term = f"%{search}%"
        params = [term, term, term, term]

    count_sql = f"SELECT COUNT(*) AS cnt FROM patients {where}"
    total = query_one(count_sql, params)["cnt"]

    rows = query_all(f"""
        SELECT * FROM patients {where}
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])

    return rows, total


def log_action(user_id, action, details=None):
    execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details),
    )


def patient_id_exists(patient_id):
    row = query_one("SELECT id FROM patients WHERE patient_id = ?", (patient_id,))
    return row is not None


def generate_patient_id():
    start = query_one("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM patients")["n"]
    for n in range(start, start + 10000):
        candidate = f"P-{n:06d}"
        if not patient_id_exists(candidate):
            return candidate
    raise RuntimeError("Could not generate a unique patient ID")
