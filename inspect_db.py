import sqlite3
conn = sqlite3.connect(r'C:\Users\narne\.gemini\antigravity\scratch\electronics_shop_system\electrodesk.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f'Total tables in live DB: {len(tables)}')
for t in tables:
    cur.execute(f'PRAGMA table_info([{t}])')
    cols = cur.fetchall()
    cur.execute(f'SELECT COUNT(*) FROM [{t}]')
    cnt = cur.fetchone()[0]
    print(f'  {t:<30s} {len(cols):3d} cols   {cnt:5d} rows')
conn.close()
