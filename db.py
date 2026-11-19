"""
Unified Database Access Layer for Electronics Shop Management System
Supports MySQL (PyMySQL) and SQLite seamlessly with automatic fallback.
"""
import os
import sqlite3
import datetime
import config

try:
    import pymysql
    import pymysql.cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False


def _get_active_db_type():
    """Determine whether to use MySQL or SQLite."""
    if config.DB_TYPE == 'mysql' and PYMYSQL_AVAILABLE:
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
        except Exception:
            # Fall back to sqlite if MySQL server is unreachable
            return 'sqlite'
    return 'sqlite'


ACTIVE_DB_TYPE = _get_active_db_type()


def get_connection():
    """Returns a new database connection."""
    global ACTIVE_DB_TYPE
    if ACTIVE_DB_TYPE == 'mysql':
        try:
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
        except Exception as e:
            # If MySQL fails at runtime, switch to SQLite
            ACTIVE_DB_TYPE = 'sqlite'

    conn = sqlite3.connect(config.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _adapt_sql(sql):
    """
    Translates standard %s placeholder SQL to ? when using SQLite.
    Also handles MySQL/SQLite function compatibility (e.g., NOW(), IFNULL).
    """
    if ACTIVE_DB_TYPE == 'sqlite':
        # Replace %s with ? for parameterized queries
        sql = sql.replace('%s', '?')
        # Standardize common functions
        sql = sql.replace('NOW()', "datetime('now', 'localtime')")
        sql = sql.replace('CURDATE()', "date('now', 'localtime')")
    return sql


def _row_to_dict(row):
    """Convert an sqlite3.Row or PyMySQL row to a standard python dict."""
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        d = dict(row)
        # Ensure Decimal/datetime string formatting if needed
        return d
    elif isinstance(row, dict):
        return row
    return dict(row)


def query(sql, params=()):
    """
    Execute a SELECT query and return all matching rows as a list of dicts.
    """
    conn = get_connection()
    try:
        adapted_sql = _adapt_sql(sql)
        cursor = conn.cursor()
        cursor.execute(adapted_sql, params)
        rows = cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql, params=()):
    """
    Execute a SELECT query and return the first matching row as a dict, or None.
    """
    conn = get_connection()
    try:
        adapted_sql = _adapt_sql(sql)
        cursor = conn.cursor()
        cursor.execute(adapted_sql, params)
        row = cursor.fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def execute(sql, params=(), return_id=False):
    """
    Execute an INSERT, UPDATE, or DELETE query and commit the transaction.
    Returns lastrowid if return_id=True, else rowcount.
    """
    conn = get_connection()
    try:
        adapted_sql = _adapt_sql(sql)
        cursor = conn.cursor()
        cursor.execute(adapted_sql, params)
        conn.commit()
        if return_id:
            return cursor.lastrowid
        return cursor.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_transaction(operations):
    """
    Executes multiple SQL operations in a single atomic transaction.
    `operations` is a list of tuples: (sql_statement, params_tuple)
    Returns last inserted ID of the final operation if available.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        last_id = None
        for item in operations:
            if len(item) == 2:
                sql, params = item
            else:
                sql = item[0]
                params = ()
            adapted_sql = _adapt_sql(sql)
            cursor.execute(adapted_sql, params)
            last_id = cursor.lastrowid
        conn.commit()
        return last_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_db_info():
    """Return database type and status for display in admin/footer."""
    return {
        'type': ACTIVE_DB_TYPE.upper(),
        'target': config.MYSQL_DB if ACTIVE_DB_TYPE == 'mysql' else os.path.basename(config.SQLITE_DB_PATH)
    }
