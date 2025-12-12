from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'projects.db')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

app = Flask(__name__)
app.config['DATABASE'] = DATABASE
app.secret_key = SECRET_KEY

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database from schema.sql"""
    with app.open_resource('schema.sql') as f:
        sql = f.read().decode('utf8')
    db = get_db()
    db.executescript(sql)
    db.commit()
    print('Initialized the database.')

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role']
        if not username or not password or role not in ('student','teacher'):
            flash('Заповніть усі поля правильно.')
            return redirect(url_for('register'))
        hashed = generate_password_hash(password)
        try:
            execute_db("INSERT INTO users (username, password, role) VALUES (?,?,?)", (username, hashed, role))
            flash('Реєстрація пройшла успішно. Увійдіть.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Користувач з таким іменем уже існує.')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        flash('Невірний логін або пароль.')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    role = session['role']
    if role == 'student':
        projects = query_db("SELECT p.*, u.username as owner FROM projects p JOIN users u ON p.owner_id = u.id WHERE owner_id = ? ORDER BY updated_at DESC", (user_id,))
    else:
        projects = query_db("SELECT p.*, u.username as owner FROM projects p JOIN users u ON p.owner_id = u.id ORDER BY updated_at DESC")
    return render_template('dashboard.html', projects=projects, role=role)

@app.route('/project/create', methods=['GET','POST'])
def project_create():
    if 'user_id' not in session or session.get('role') != 'student':
        flash('Тільки студенти можуть створювати проєкти.')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form['title'].strip()
        desc = request.form.get('description','').strip()
        status = request.form.get('status','planned')
        if not title:
            flash('Дайте назву проєкту.')
            return redirect(url_for('project_create'))
        execute_db("INSERT INTO projects (title, description, owner_id, status) VALUES (?,?,?,?)",
                   (title, desc, session['user_id'], status))
        flash('Проєкт створено.')
        return redirect(url_for('dashboard'))
    return render_template('project_create.html')

@app.route('/project/<int:pid>')
def project_view(pid):
    proj = query_db("SELECT p.*, u.username as owner FROM projects p JOIN users u ON p.owner_id = u.id WHERE p.id = ?", (pid,), one=True)
    if not proj:
        flash('Проєкт не знайдено.')
        return redirect(url_for('dashboard'))
    comments = query_db("SELECT c.*, u.username as author FROM comments c JOIN users u ON c.author_id = u.id WHERE project_id = ? ORDER BY created_at", (pid,))
    grades = query_db("SELECT g.*, u.username as teacher FROM grades g JOIN users u ON g.teacher_id = u.id WHERE project_id = ? ORDER BY created_at", (pid,))
    return render_template('project_view.html', project=proj, comments=comments, grades=grades)

@app.route('/project/<int:pid>/comment', methods=['POST'])
def project_comment(pid):
    if 'user_id' not in session:
        flash('Увійдіть, будь ласка.')
        return redirect(url_for('login'))
    content = request.form.get('content','').strip()
    if not content:
        flash('Коментар не може бути пустим.')
        return redirect(url_for('project_view', pid=pid))
    execute_db("INSERT INTO comments (project_id, author_id, content) VALUES (?,?,?)", (pid, session['user_id'], content))
    flash('Коментар додано.')
    return redirect(url_for('project_view', pid=pid))

@app.route('/project/<int:pid>/grade', methods=['POST'])
def project_grade(pid):
    if 'user_id' not in session or session.get('role') != 'teacher':
        flash('Тільки викладачі можуть ставити оцінки.')
        return redirect(url_for('project_view', pid=pid))
    try:
        score = int(request.form['score'])
    except (ValueError, TypeError):
        flash('Невірний формат оцінки.')
        return redirect(url_for('project_view', pid=pid))
    comment = request.form.get('comment','').strip()
    if score < 0 or score > 100:
        flash('Оцінка повинна бути від 0 до 100.')
        return redirect(url_for('project_view', pid=pid))
    execute_db("INSERT INTO grades (project_id, teacher_id, score, comment) VALUES (?,?,?,?)", (pid, session['user_id'], score, comment))
    flash('Оцінку додано.')
    return redirect(url_for('project_view', pid=pid))

@app.route('/project/<int:pid>/edit', methods=['GET','POST'])
def project_edit(pid):
    proj = query_db("SELECT * FROM projects WHERE id = ?", (pid,), one=True)
    if not proj:
        flash('Проєкт не знайдено.')
        return redirect(url_for('dashboard'))
    if 'user_id' not in session or session['user_id'] != proj['owner_id']:
        flash('Ви не маєте прав редагувати цей проєкт.')
        return redirect(url_for('project_view', pid=pid))
    if request.method == 'POST':
        title = request.form['title'].strip()
        desc = request.form.get('description','').strip()
        status = request.form.get('status','planned')
        if not title:
            flash('Невірні дані.')
            return redirect(url_for('project_edit', pid=pid))
        db = get_db()
        db.execute("UPDATE projects SET title=?, description=?, status=?, updated_at=? WHERE id=?",
                   (title, desc, status, datetime.utcnow(), pid))
        db.commit()
        flash('Проєкт оновлено.')
        return redirect(url_for('project_view', pid=pid))
    return render_template('project_edit.html', project=proj)

if __name__ == '__main__':
    app.run(debug=True)
