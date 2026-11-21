"""
Unified Database Access Layer for Electronics Shop Management System
Supports MySQL (PyMySQL) and SQLite seamlessly with automatic fallback at start-up.

Fixes vs. previous version:
  * Runtime MySQL failures are no longer silently redirected to SQLite
    (that wrote data into a different database without warning).
  * DECIMAL values coming back from MySQL are converted to float so arithmetic
    in the application layer works identically on both engines.
  * `transaction()` context manager gives real atomic multi-statement work
    (with `BEGIN IMMEDIATE` on SQLite to serialise concurrent writers).
  * Queries without parameters are sent without a parameter tuple so literal
    `%` characters (e.g. DATE_FORMAT) are safe on MySQL.
"""
import os
import re
import sqlite3
import decimal
import logging
import config

log = logging.getLogger('electrodesk.db')

try:
    import pymysql
    import pymysql.cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False


def _get_active_db_type():
    """Determine whether to use MySQL or SQLite (decided once at start-up)."""
    if config.DB_TYPE == 'mysql':
        if not PYMYSQL_AVAILABLE:
            log.warning("DB_TYPE=mysql but PyMySQL is not installed - using SQLite.")
            return 'sqlite'
        try:
            conn = pymysql.connect(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                connect_timeout=2
            )
            conn.close()
            return 'mysql'
        except Exception as e:
            log.warning("MySQL unreachable at start-up (%s) - using SQLite.", e)
            return 'sqlite'
    return 'sqlite'


ACTIVE_DB_TYPE = _get_active_db_type()


def is_mysql():
    return ACTIVE_DB_TYPE == 'mysql'


def get_connection():
    """Returns a new database connection for the engine chosen at start-up."""
    if ACTIVE_DB_TYPE == 'mysql':
        return pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )

    conn = sqlite3.connect(config.SQLITE_DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _adapt_sql(sql):
    """
    Translates standard %s placeholder SQL to ? when using SQLite.
    Also handles MySQL/SQLite function compatibility (e.g., NOW()).
    """
    if ACTIVE_DB_TYPE == 'sqlite':
        sql = sql.replace('%s', '?')
        sql = sql.replace('NOW()', "datetime('now', 'localtime')")
        sql = sql.replace('CURDATE()', "date('now', 'localtime')")
    return sql


def month_expr(column):
    """Engine-neutral 'YYYY-MM' expression for a date/datetime column."""
    return f"SUBSTR({column}, 1, 7)"


def _clean(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def _row_to_dict(row):
    """Convert an sqlite3.Row or PyMySQL row to a standard python dict."""
    if row is None:
        return None
    d = dict(row)
    return {k: _clean(v) for k, v in d.items()}


def _run(cursor, sql, params):
    """Execute adapting SQL; omit the params tuple when there are none."""
    adapted = _adapt_sql(sql)
    if params:
        cursor.execute(adapted, params)
    elif ACTIVE_DB_TYPE == 'mysql':
        cursor.execute(adapted)
    else:
        cursor.execute(adapted, ())
    return cursor


def query(sql, params=()):
    """Execute a SELECT query and return all matching rows as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _run(cursor, sql, params or ())
        return [_row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def query_one(sql, params=()):
    """Execute a SELECT query and return the first matching row as a dict, or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _run(cursor, sql, params or ())
        return _row_to_dict(cursor.fetchone())
    finally:
        conn.close()


def execute(sql, params=(), return_id=False):
    """
    Execute an INSERT, UPDATE, or DELETE query and commit the transaction.
    Returns lastrowid if return_id=True, else rowcount.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _run(cursor, sql, params or ())
        conn.commit()
        return cursor.lastrowid if return_id else cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_transaction(operations):
    """
    Executes multiple SQL operations in a single atomic transaction.
    `operations` is a list of tuples: (sql_statement, params_tuple)
    Returns last inserted ID of the final operation if available.
    """
    with transaction() as tx:
        last_id = None
        for item in operations:
            sql = item[0]
            params = item[1] if len(item) > 1 else ()
            tx.execute(sql, params)
            last_id = tx.lastrowid
        return last_id


class Transaction:
    """Handle passed to `with transaction() as tx:` blocks."""

    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        _run(self.cursor, sql, params or ())
        self.lastrowid = self.cursor.lastrowid
        self.rowcount = self.cursor.rowcount
        return self.rowcount

    def query(self, sql, params=()):
        _run(self.cursor, sql, params or ())
        return [_row_to_dict(r) for r in self.cursor.fetchall()]

    def query_one(self, sql, params=()):
        _run(self.cursor, sql, params or ())
        return _row_to_dict(self.cursor.fetchone())

    def columns(self, table):
        """Column names of a table (table name must be a trusted constant)."""
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
            raise ValueError('Bad table name')
        self.cursor.execute(f"SELECT * FROM {table} LIMIT 0")
        return [d[0] for d in self.cursor.description]


class _TxContext:
    def __enter__(self):
        self.conn = get_connection()
        try:
            if ACTIVE_DB_TYPE == 'sqlite':
                # Take the write lock up-front so stock checks and updates
                # inside the block cannot interleave with another writer.
                self.conn.isolation_level = None
                self.conn.execute("BEGIN IMMEDIATE")
            self.tx = Transaction(self.conn)
        except Exception:
            self.conn.close()
            raise
        return self.tx

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                if ACTIVE_DB_TYPE == 'sqlite':
                    self.conn.execute("COMMIT")
                else:
                    self.conn.commit()
            else:
                if ACTIVE_DB_TYPE == 'sqlite':
                    self.conn.execute("ROLLBACK")
                else:
                    self.conn.rollback()
        finally:
            self.conn.close()
        return False


def transaction():
    """
    Atomic transaction context manager:

        with db.transaction() as tx:
            tx.execute("UPDATE ...", (...))
            row = tx.query_one("SELECT ...", (...))

    Commits when the block exits normally, rolls back on any exception.
    """
    return _TxContext()


def upsert_setting(key, value):
    """Engine-neutral insert-or-update for STORE_SETTING."""
    with transaction() as tx:
        if tx.query_one("SELECT 1 AS x FROM STORE_SETTING WHERE setting_key = %s", (key,)):
            tx.execute("UPDATE STORE_SETTING SET setting_value = %s WHERE setting_key = %s", (value, key))
        else:
            tx.execute("INSERT INTO STORE_SETTING (setting_key, setting_value) VALUES (%s, %s)", (key, value))


def get_db_info():
    """Return database type and status for display in admin/footer."""
    return {
        'type': ACTIVE_DB_TYPE.upper(),
        'target': config.MYSQL_DB if ACTIVE_DB_TYPE == 'mysql' else os.path.basename(config.SQLITE_DB_PATH)
    }
