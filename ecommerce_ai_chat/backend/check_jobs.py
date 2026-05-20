import sqlite3
conn = sqlite3.connect("ecommerce_chat.db")
rows = conn.execute("SELECT id, status, stage, progress, error_msg FROM video_jobs ORDER BY created_at DESC LIMIT 5").fetchall()
for r in rows:
    err = (r[4] or "")[:80]
    print(f"ID: {r[0][:12]}... | {r[1]:12} | {r[3] or '':35} | {r[2]:3}% | {err}")
conn.close()
