import sqlite3

DB_FILE = "backend/jobs.db"

connection = sqlite3.connect(DB_FILE)

cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    playbook TEXT NOT NULL,
    inventory TEXT NOT NULL,
    extra_vars TEXT,
    command TEXT,
    return_code INTEGER,
    output TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
)
""")

connection.commit()

connection.close()

print("Jobs table created successfully.")