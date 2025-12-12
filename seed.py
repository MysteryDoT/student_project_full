# Seed script to create sample users and projects after initializing the DB.
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('projects.db')
c = conn.cursor()

users = [
    ('alice', generate_password_hash('password1'), 'student'),
    ('bob', generate_password_hash('password2'), 'student'),
    ('prof', generate_password_hash('teachpass'), 'teacher'),
]

for u in users:
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", u)
    except sqlite3.IntegrityError:
        pass

# create example projects
c.execute("SELECT id FROM users WHERE username='alice'")
row = c.fetchone()
if row:
    alice_id = row[0]
    c.execute("INSERT OR IGNORE INTO projects (id, title, description, owner_id, status) VALUES (1, 'Проєкт A', 'Опис проєкту A', ?, 'in_progress')", (alice_id,))

c.execute("SELECT id FROM users WHERE username='bob'")
row = c.fetchone()
if row:
    bob_id = row[0]
    c.execute("INSERT OR IGNORE INTO projects (id, title, description, owner_id, status) VALUES (2, 'Проєкт B', 'Опис проєкту B', ?, 'planned')", (bob_id,))

conn.commit()
conn.close()
print('Seed completed.')
