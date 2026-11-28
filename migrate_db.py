"""
migrate_db.py — Non-destructive schema migration for electrodesk.db

Steps:
  1. Back up electrodesk.db -> electrodesk.db.migrate_backup_<timestamp>
  2. Parse SQLITE_SCHEMA from init_db.py
  3. For each table in schema:
       - If table does not exist  → CREATE TABLE
       - If table exists          → find missing columns → ALTER TABLE ADD COLUMN
  4. Print a summary of all changes made
"""
import os
import re
import sys
import shutil
import sqlite3
import datetime

BASE = r"C:\Users\narne\.gemini\antigravity\scratch\electronics_shop_system"
DB_PATH   = os.path.join(BASE, "electrodesk.db")
INIT_PATH = os.path.join(BASE, "init_db.py")

# ── 1. Backup ────────────────────────────────────────────────────────────────
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = DB_PATH + f".migrate_backup_{ts}"
shutil.copy2(DB_PATH, backup_path)
print(f"[BACKUP] {backup_path}")

# ── 2. Extract SQLITE_SCHEMA from init_db.py ─────────────────────────────────
src = open(INIT_PATH, encoding="utf-8").read()
m = re.search(r'SQLITE_SCHEMA\s*=\s*"""(.*?)"""', src, re.DOTALL)
if not m:
    print("ERROR: Could not find SQLITE_SCHEMA in init_db.py")
    sys.exit(1)
schema_sql = m.group(1)

# ── 3. Parse CREATE TABLE blocks ─────────────────────────────────────────────
# Extract each CREATE TABLE ... ; block
table_blocks = re.findall(
    r"(CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\(.*?\);)",
    schema_sql,
    re.DOTALL | re.IGNORECASE,
)

def parse_columns(create_sql):
    """Return list of (col_name, col_def_line) from a CREATE TABLE statement."""
    # Extract content between first ( and last )
    inner = re.search(r"\((.*)\)", create_sql, re.DOTALL)
    if not inner:
        return []
    body = inner.group(1)
    cols = []
    for line in body.split("\n"):
        line = line.strip().rstrip(",")
        if not line:
            continue
        # Skip table constraints
        if re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK|CONSTRAINT)", line, re.IGNORECASE):
            continue
        # First token is column name
        col_name = re.split(r"\s+", line)[0]
        if col_name:
            cols.append((col_name, line))
    return cols

# ── 4. Connect and apply migrations ─────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = OFF;")
cur = conn.cursor()

# Get existing tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
existing_tables = {row[0] for row in cur.fetchall()}

created_tables  = []
added_columns   = []
unchanged_tables = []

for create_sql, table_name in table_blocks:
    if table_name not in existing_tables:
        # Create the whole table
        try:
            cur.executescript(create_sql)
            created_tables.append(table_name)
            print(f"[CREATE TABLE] {table_name}")
        except Exception as e:
            print(f"[ERROR] Creating {table_name}: {e}")
    else:
        # Check for missing columns
        cur.execute(f"PRAGMA table_info({table_name})")
        live_cols = {row[1].lower() for row in cur.fetchall()}

        schema_cols = parse_columns(create_sql)
        new_cols = [(n, d) for n, d in schema_cols if n.lower() not in live_cols]

        if new_cols:
            for col_name, col_def in new_cols:
                # ALTER TABLE only supports adding one column at a time
                # Strip any inline FK references for ALTER TABLE compatibility
                col_def_clean = re.sub(r'\s+REFERENCES\s+\w+\([^)]+\)', '', col_def)
                # Remove trailing comma if any
                col_def_clean = col_def_clean.rstrip(",")
                try:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_def_clean}"
                    cur.execute(alter_sql)
                    added_columns.append((table_name, col_name, col_def_clean))
                    print(f"[ADD COLUMN]   {table_name}.{col_name}  →  {col_def_clean}")
                except Exception as e:
                    print(f"[ERROR] ALTER {table_name}.{col_name}: {e}")
        else:
            unchanged_tables.append(table_name)

conn.commit()
conn.execute("PRAGMA foreign_keys = ON;")
conn.close()

# ── 5. Summary ───────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("MIGRATION SUMMARY")
print("=" * 60)
print(f"  Backup:          {os.path.basename(backup_path)}")
print(f"  Tables CREATED:  {len(created_tables)}")
for t in created_tables:
    print(f"    + {t}")
print(f"  Columns ADDED:   {len(added_columns)}")
for tbl, col, defn in added_columns:
    print(f"    + {tbl}.{col}")
print(f"  Tables unchanged: {len(unchanged_tables)}")
print("=" * 60)
if not created_tables and not added_columns:
    print("  No schema changes needed — DB is already up to date.")
