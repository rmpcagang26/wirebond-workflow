"""
Wire Bond Group - Activity Flow System
A local activity tracking system for Wire Bond Group shifting engineers.
"""

import os
import sys
import sqlite3
import secrets
import uuid
import math
import calendar
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_from_directory, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
# When bundled with PyInstaller:
#   BUNDLE_DIR → _MEIPASS (read-only: templates, static, .py code)
#   DATA_DIR   → folder containing the .exe (writable: database, uploads)
# When running as a plain script both point to the project folder.
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS                       # bundled resources
    DATA_DIR   = os.path.dirname(sys.executable)   # next to the .exe
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR   = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = DATA_DIR  # alias kept for backward-compat (used by secret key + uploads)

app = Flask(__name__,
            template_folder=os.path.join(BUNDLE_DIR, 'templates'),
            static_folder=os.path.join(BUNDLE_DIR, 'static'))

# Persist secret key so sessions survive server restarts
_secret_file = os.path.join(BASE_DIR, 'data', '.secret_key')
if os.path.exists(_secret_file):
    with open(_secret_file, 'r') as f:
        app.secret_key = f.read().strip()
else:
    os.makedirs(os.path.dirname(_secret_file), exist_ok=True)
    _key = secrets.token_hex(32)
    with open(_secret_file, 'w') as f:
        f.write(_key)
    app.secret_key = _key

app.config.update(
    UPLOAD_PHOTOS=os.path.join(BASE_DIR, 'uploads', 'photos'),
    UPLOAD_FILES=os.path.join(BASE_DIR, 'uploads', 'files'),
    DATABASE=os.path.join(BASE_DIR, 'data', 'wirebond.db'),
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50 MB
)

ALLOWED_PHOTO_EXT = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_FILE_EXT = {'xlsx', 'xls', 'pptx', 'ppt', 'pdf', 'docx', 'doc', 'csv', 'txt'}

# 4 rotating shifts (12-hour): Day 6:30-18:30, Night 18:30-6:30
# DS = Day Shift: Mon-Thu 08:00-18:15, Fri 08:00-13:00, Sat-Sun off
SHIFTS = ['A', 'B', 'C', 'D', 'DS']

PROGRESS_TYPES = {
    'none':          'No Progress Tracking',
    'machine_count': 'Machine Number Based',
    'checklist':     'Checklist Based',
    'units_bonded':  'Units Bonded Progress',
    'done_not_done': 'Done / Not Yet',
    'custom':        'Custom Percentage',
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables, migrate columns, and seed default admin."""
    db = sqlite3.connect(app.config['DATABASE'])
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT    UNIQUE NOT NULL,
        password    TEXT    NOT NULL,
        full_name   TEXT    NOT NULL,
        role        TEXT    DEFAULT 'user',
        shift       TEXT    DEFAULT 'A',
        is_active   INTEGER DEFAULT 1,
        created_at  TEXT    DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS activities (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        title           TEXT    NOT NULL,
        customer        TEXT,
        device          TEXT,
        category        TEXT,
        description     TEXT,
        status          TEXT    DEFAULT 'active',
        priority        TEXT    DEFAULT 'normal',
        is_urgent       INTEGER DEFAULT 0,
        due_date        TEXT,
        progress_type   TEXT    DEFAULT 'none',
        progress_total  REAL    DEFAULT 0,
        progress_current REAL   DEFAULT 0,
        progress_unit   TEXT    DEFAULT '',
        created_by      INTEGER,
        created_at      TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS checklist_items (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id   INTEGER NOT NULL,
        item_text     TEXT    NOT NULL,
        is_completed  INTEGER DEFAULT 0,
        completed_by  INTEGER,
        completed_at  TEXT,
        sort_order    INTEGER DEFAULT 0,
        FOREIGN KEY (activity_id) REFERENCES activities(id),
        FOREIGN KEY (completed_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS activity_updates (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id  INTEGER NOT NULL,
        user_id      INTEGER NOT NULL,
        update_text  TEXT    NOT NULL,
        shift        TEXT,
        created_at   TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (activity_id) REFERENCES activities(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS update_photos (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        update_id        INTEGER NOT NULL,
        filename         TEXT    NOT NULL,
        original_name    TEXT,
        created_at       TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (update_id) REFERENCES activity_updates(id)
    );

    CREATE TABLE IF NOT EXISTS update_files (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        update_id        INTEGER,
        activity_id      INTEGER,
        filename         TEXT    NOT NULL,
        original_name    TEXT,
        file_type        TEXT,
        created_at       TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (update_id) REFERENCES activity_updates(id),
        FOREIGN KEY (activity_id) REFERENCES activities(id)
    );

    CREATE TABLE IF NOT EXISTS email_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        shift     TEXT,
        sent_by   INTEGER,
        subject   TEXT,
        body_html TEXT,
        sent_at   TEXT DEFAULT (datetime('now','localtime')),
        status    TEXT,
        FOREIGN KEY (sent_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS announcements (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        content     TEXT,
        priority    TEXT    DEFAULT 'info',
        is_active   INTEGER DEFAULT 1,
        expires_at  TEXT,
        created_by  INTEGER,
        created_at  TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS public_holidays (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL UNIQUE,
        name        TEXT    NOT NULL,
        created_by  INTEGER,
        created_at  TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS shift_calendar_overrides (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        date           TEXT    NOT NULL,
        crew           TEXT    NOT NULL,
        override_type  TEXT    NOT NULL,
        note           TEXT,
        created_by     INTEGER,
        created_at     TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS mentions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id  INTEGER NOT NULL,
        user_id      INTEGER NOT NULL,
        message      TEXT,
        is_read      INTEGER DEFAULT 0,
        created_by   INTEGER,
        created_at   TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (activity_id) REFERENCES activities(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS user_schedule_overrides (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        user_id     INTEGER NOT NULL,
        type        TEXT    NOT NULL,
        note        TEXT,
        created_by  INTEGER,
        created_at  TEXT    DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    );
    """)

    # ---- Migrate: add progress columns to activities if missing ----------
    cols = [r[1] for r in db.execute("PRAGMA table_info(activities)").fetchall()]
    for col, typedef in [
        ('progress_type',    "TEXT DEFAULT 'none'"),
        ('progress_total',   "REAL DEFAULT 0"),
        ('progress_current', "REAL DEFAULT 0"),
        ('progress_unit',    "TEXT DEFAULT ''"),
        ('target_engineers', "TEXT DEFAULT 'Both'"),
    ]:
        if col not in cols:
            db.execute(f"ALTER TABLE activities ADD COLUMN {col} {typedef}")

    # ---- Migrate: add engineer_type column to users if missing ------------
    user_cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    if 'engineer_type' not in user_cols:
        db.execute("ALTER TABLE users ADD COLUMN engineer_type TEXT DEFAULT 'Process'")

    # Create default admin if not exists
    existing = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, password, full_name, role, shift) VALUES (?, ?, ?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 'Administrator', 'admin', 'A')
        )
        db.commit()
        print("[INIT] Default admin created  ->  username: admin  |  password: admin123")

    db.close()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def current_shift():
    """Return the logged-in user's assigned shift letter."""
    return session.get('shift', 'A')


def current_time_slot():
    """Return 'Day', 'Night', or 'Off' based on user's shift type and current time."""
    now = datetime.now()
    shift = session.get('shift', 'A')

    if shift == 'DS':
        # Day Shift: Mon-Thu 08:00-18:15, Fri 08:00-13:00, Sat-Sun off
        weekday = now.weekday()          # 0=Mon … 6=Sun
        t = now.hour + now.minute / 60.0
        if weekday <= 3:                 # Monday – Thursday
            return 'Day' if 8.0 <= t < 18.25 else 'Off'
        elif weekday == 4:               # Friday
            return 'Day' if 8.0 <= t < 13.0 else 'Off'
        else:                            # Saturday – Sunday
            return 'Off'

    # Rotating shifts A/B/C/D — 6:30 boundary
    t = now.hour + now.minute / 60.0
    return 'Day' if 6.5 <= t < 18.5 else 'Night'


def calc_progress(activity, db=None):
    """Return progress percentage (0-100) for an activity."""
    ptype = activity['progress_type'] or 'none'
    if ptype == 'none':
        return None
    if ptype == 'done_not_done':
        return 100.0 if activity['progress_current'] >= 1 else 0.0
    if ptype == 'checklist' and db:
        total = db.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE activity_id=?",
            (activity['id'],)
        ).fetchone()[0]
        done = db.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE activity_id=? AND is_completed=1",
            (activity['id'],)
        ).fetchone()[0]
        return round(done / total * 100, 1) if total > 0 else 0.0
    if ptype in ('machine_count', 'units_bonded', 'custom'):
        total = activity['progress_total']
        current = activity['progress_current']
        if ptype == 'custom':
            return min(max(current, 0), 100)
        return round(current / total * 100, 1) if total > 0 else 0.0
    return 0.0


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def allowed_photo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PHOTO_EXT


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_FILE_EXT


def save_photo_as_jpeg(file_storage):
    unique = uuid.uuid4().hex[:12]
    jpeg_name = f"{unique}.jpg"
    save_path = os.path.join(app.config['UPLOAD_PHOTOS'], jpeg_name)
    if PIL_AVAILABLE:
        img = Image.open(file_storage.stream)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(save_path, 'JPEG', quality=85, optimize=True)
    else:
        file_storage.save(save_path)
    return jpeg_name


def save_attachment(file_storage, activity_id):
    original = secure_filename(file_storage.filename)
    unique = uuid.uuid4().hex[:8]
    safe_name = f"{unique}_{original}"
    activity_dir = os.path.join(app.config['UPLOAD_FILES'], str(activity_id))
    os.makedirs(activity_dir, exist_ok=True)
    file_storage.save(os.path.join(activity_dir, safe_name))
    return safe_name


# ---------------------------------------------------------------------------
# Context processor – available in every template
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    unread = 0
    if 'user_id' in session:
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) AS cnt FROM mentions WHERE user_id = ? AND is_read = 0",
            (session['user_id'],)
        ).fetchone()
        unread = row['cnt'] if row else 0
    # Active announcements
    announcements = []
    if 'user_id' in session:
        announcements = db.execute(
            "SELECT a.*, u.full_name AS author_name FROM announcements a "
            "LEFT JOIN users u ON a.created_by = u.id "
            "WHERE a.is_active = 1 AND (a.expires_at IS NULL OR a.expires_at >= datetime('now','localtime')) "
            "ORDER BY CASE a.priority WHEN 'urgent' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, a.created_at DESC"
        ).fetchall()

    return dict(
        current_shift=current_shift(),
        time_slot=current_time_slot(),
        now=datetime.now(),
        unread_mentions=unread,
        progress_types=PROGRESS_TYPES,
        shifts=SHIFTS,
        announcements=announcements,
    )


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
        ).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['shift'] = user['shift']
            session['engineer_type'] = user['engineer_type'] if 'engineer_type' in user.keys() else 'Process'
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    status_filter = request.args.get('status', 'all')
    search_q = request.args.get('q', '').strip()

    query = """
        SELECT a.*,
               u.full_name AS created_by_name,
               (SELECT COUNT(*) FROM activity_updates WHERE activity_id = a.id) AS update_count,
               (SELECT au.update_text FROM activity_updates au
                WHERE au.activity_id = a.id ORDER BY au.created_at DESC LIMIT 1) AS latest_update,
               (SELECT au.created_at FROM activity_updates au
                WHERE au.activity_id = a.id ORDER BY au.created_at DESC LIMIT 1) AS latest_update_at,
               (SELECT u2.full_name FROM activity_updates au
                JOIN users u2 ON au.user_id = u2.id
                WHERE au.activity_id = a.id ORDER BY au.created_at DESC LIMIT 1) AS latest_update_by
        FROM activities a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE 1=1
    """
    params = []
    if status_filter and status_filter != 'all':
        query += " AND a.status = ?"
        params.append(status_filter)
    if search_q:
        query += " AND (a.title LIKE ? OR a.customer LIKE ? OR a.device LIKE ?)"
        like = f"%{search_q}%"
        params.extend([like, like, like])
    query += " ORDER BY a.is_urgent DESC, a.priority DESC, a.created_at DESC"
    activities_raw = db.execute(query, params).fetchall()

    # Compute progress for each activity
    activities = []
    for a in activities_raw:
        progress = calc_progress(a, db)
        activities.append({'row': a, 'progress': progress})

    # Stats
    total = db.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM activities WHERE status='active'").fetchone()[0]
    overdue = db.execute("SELECT COUNT(*) FROM activities WHERE status='overdue'").fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM activities WHERE status='completed'").fetchone()[0]

    return render_template('dashboard.html',
                           activities=activities,
                           stats={'total': total, 'active': active, 'overdue': overdue, 'completed': completed},
                           status_filter=status_filter,
                           search_q=search_q)


# ---------------------------------------------------------------------------
# ACTIVITY DETAIL & UPDATES
# ---------------------------------------------------------------------------

@app.route('/activity/<int:activity_id>')
@login_required
def activity_detail(activity_id):
    db = get_db()
    activity = db.execute(
        "SELECT a.*, u.full_name AS created_by_name FROM activities a "
        "LEFT JOIN users u ON a.created_by = u.id WHERE a.id = ?",
        (activity_id,)
    ).fetchone()
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('dashboard'))

    progress = calc_progress(activity, db)

    updates = db.execute("""
        SELECT au.*, u.full_name AS user_name, u.shift AS user_shift
        FROM activity_updates au
        JOIN users u ON au.user_id = u.id
        WHERE au.activity_id = ?
        ORDER BY au.created_at DESC
    """, (activity_id,)).fetchall()

    updates_with_media = []
    for upd in updates:
        photos = db.execute("SELECT * FROM update_photos WHERE update_id = ?", (upd['id'],)).fetchall()
        files = db.execute("SELECT * FROM update_files WHERE update_id = ?", (upd['id'],)).fetchall()
        updates_with_media.append({'entry': upd, 'photos': photos, 'files': files})

    activity_files = db.execute(
        "SELECT * FROM update_files WHERE activity_id = ? AND update_id IS NULL", (activity_id,)
    ).fetchall()

    checklist = db.execute(
        "SELECT ci.*, u.full_name AS completed_by_name FROM checklist_items ci "
        "LEFT JOIN users u ON ci.completed_by = u.id "
        "WHERE ci.activity_id = ? ORDER BY ci.sort_order, ci.id",
        (activity_id,)
    ).fetchall()

    return render_template('activity_detail.html',
                           activity=activity,
                           progress=progress,
                           updates=updates_with_media,
                           activity_files=activity_files,
                           checklist=checklist)


@app.route('/activity/<int:activity_id>/update', methods=['POST'])
@login_required
def add_update(activity_id):
    db = get_db()
    update_text = request.form.get('update_text', '').strip()
    if not update_text:
        flash('Update text cannot be empty.', 'warning')
        return redirect(url_for('activity_detail', activity_id=activity_id))

    shift = current_shift()
    cursor = db.execute(
        "INSERT INTO activity_updates (activity_id, user_id, update_text, shift) VALUES (?, ?, ?, ?)",
        (activity_id, session['user_id'], update_text, shift)
    )
    update_id = cursor.lastrowid

    for photo in request.files.getlist('photos'):
        if photo and photo.filename and allowed_photo(photo.filename):
            jpeg_name = save_photo_as_jpeg(photo)
            db.execute("INSERT INTO update_photos (update_id, filename, original_name) VALUES (?, ?, ?)",
                       (update_id, jpeg_name, photo.filename))

    for f in request.files.getlist('files'):
        if f and f.filename and allowed_file(f.filename):
            saved_name = save_attachment(f, activity_id)
            ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else ''
            db.execute("INSERT INTO update_files (update_id, activity_id, filename, original_name, file_type) VALUES (?, ?, ?, ?, ?)",
                       (update_id, activity_id, saved_name, f.filename, ext))

    db.commit()
    flash('Update logged successfully!', 'success')
    return redirect(url_for('activity_detail', activity_id=activity_id))


# ---------------------------------------------------------------------------
# PROGRESS UPDATE ROUTES
# ---------------------------------------------------------------------------

@app.route('/activity/<int:activity_id>/progress', methods=['POST'])
@login_required
def update_progress(activity_id):
    db = get_db()
    activity = db.execute("SELECT * FROM activities WHERE id=?", (activity_id,)).fetchone()
    if not activity:
        flash('Activity not found.', 'danger')
        return redirect(url_for('dashboard'))

    ptype = activity['progress_type']

    if ptype in ('machine_count', 'units_bonded'):
        new_val = request.form.get('progress_current', type=float, default=0)
        db.execute("UPDATE activities SET progress_current=? WHERE id=?", (new_val, activity_id))
    elif ptype == 'custom':
        new_pct = request.form.get('progress_current', type=float, default=0)
        new_pct = min(max(new_pct, 0), 100)
        db.execute("UPDATE activities SET progress_current=? WHERE id=?", (new_pct, activity_id))
    elif ptype == 'done_not_done':
        is_done = 1 if request.form.get('is_done') else 0
        db.execute("UPDATE activities SET progress_current=? WHERE id=?", (is_done, activity_id))

    db.commit()
    flash('Progress updated!', 'success')
    return redirect(url_for('activity_detail', activity_id=activity_id))


@app.route('/activity/<int:activity_id>/checklist/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_checklist(activity_id, item_id):
    db = get_db()
    item = db.execute("SELECT * FROM checklist_items WHERE id=? AND activity_id=?", (item_id, activity_id)).fetchone()
    if item:
        new_state = 0 if item['is_completed'] else 1
        db.execute(
            "UPDATE checklist_items SET is_completed=?, completed_by=?, completed_at=? WHERE id=?",
            (new_state, session['user_id'] if new_state else None,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S') if new_state else None, item_id)
        )
        db.commit()
    return redirect(url_for('activity_detail', activity_id=activity_id))


# ---------------------------------------------------------------------------
# FILE SERVING
# ---------------------------------------------------------------------------

@app.route('/uploads/photos/<filename>')
@login_required
def serve_photo(filename):
    return send_from_directory(app.config['UPLOAD_PHOTOS'], filename)


@app.route('/uploads/files/<int:activity_id>/<filename>')
@login_required
def serve_file(activity_id, filename):
    folder = os.path.join(app.config['UPLOAD_FILES'], str(activity_id))
    return send_from_directory(folder, filename)


# ---------------------------------------------------------------------------
# ADMIN – ACTIVITY MANAGEMENT
# ---------------------------------------------------------------------------

@app.route('/admin/activities')
@admin_required
def admin_activities():
    db = get_db()
    activities_raw = db.execute(
        "SELECT a.*, u.full_name AS created_by_name FROM activities a "
        "LEFT JOIN users u ON a.created_by = u.id ORDER BY a.created_at DESC"
    ).fetchall()
    activities = []
    for a in activities_raw:
        progress = calc_progress(a, db)
        activities.append({'row': a, 'progress': progress})
    users = db.execute("SELECT id, full_name, shift FROM users WHERE is_active = 1 ORDER BY full_name").fetchall()
    return render_template('admin_activities.html', activities=activities, users=users)


@app.route('/admin/activities/create', methods=['POST'])
@admin_required
def admin_create_activity():
    db = get_db()
    title = request.form.get('title', '').strip()
    customer = request.form.get('customer', '').strip()
    device = request.form.get('device', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'normal')
    due_date = request.form.get('due_date', '').strip() or None
    is_urgent = 1 if request.form.get('is_urgent') else 0
    progress_type = request.form.get('progress_type', 'none')
    progress_total = request.form.get('progress_total', type=float, default=0)
    progress_unit = request.form.get('progress_unit', '').strip()
    target_engineers = request.form.get('target_engineers', 'Both')

    if not title:
        flash('Activity title is required.', 'warning')
        return redirect(url_for('admin_activities'))

    cursor = db.execute(
        "INSERT INTO activities (title, customer, device, category, description, priority, "
        "due_date, is_urgent, progress_type, progress_total, progress_unit, target_engineers, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, customer, device, category, description, priority, due_date,
         is_urgent, progress_type, progress_total, progress_unit, target_engineers, session['user_id'])
    )
    activity_id = cursor.lastrowid

    # Create checklist items if type is checklist
    if progress_type == 'checklist':
        items_text = request.form.get('checklist_items', '').strip()
        for i, line in enumerate(items_text.split('\n')):
            line = line.strip()
            if line:
                db.execute(
                    "INSERT INTO checklist_items (activity_id, item_text, sort_order) VALUES (?, ?, ?)",
                    (activity_id, line, i)
                )

    db.commit()
    flash(f'Activity "{title}" created.', 'success')
    return redirect(url_for('admin_activities'))


@app.route('/admin/activities/<int:activity_id>/edit', methods=['POST'])
@admin_required
def admin_edit_activity(activity_id):
    db = get_db()
    title = request.form.get('title', '').strip()
    customer = request.form.get('customer', '').strip()
    device = request.form.get('device', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    status = request.form.get('status', 'active')
    priority = request.form.get('priority', 'normal')
    due_date = request.form.get('due_date', '').strip() or None
    is_urgent = 1 if request.form.get('is_urgent') else 0
    progress_type = request.form.get('progress_type', 'none')
    progress_total = request.form.get('progress_total', type=float, default=0)
    progress_unit = request.form.get('progress_unit', '').strip()
    target_engineers = request.form.get('target_engineers', 'Both')

    db.execute("""
        UPDATE activities SET title=?, customer=?, device=?, category=?, description=?,
        status=?, priority=?, due_date=?, is_urgent=?, progress_type=?, progress_total=?,
        progress_unit=?, target_engineers=? WHERE id=?
    """, (title, customer, device, category, description, status, priority,
          due_date, is_urgent, progress_type, progress_total, progress_unit, target_engineers, activity_id))
    db.commit()
    flash('Activity updated.', 'success')
    return redirect(url_for('admin_activities'))


@app.route('/admin/activities/<int:activity_id>/delete', methods=['POST'])
@admin_required
def admin_delete_activity(activity_id):
    db = get_db()
    db.execute("DELETE FROM update_photos WHERE update_id IN (SELECT id FROM activity_updates WHERE activity_id=?)", (activity_id,))
    db.execute("DELETE FROM update_files WHERE activity_id=?", (activity_id,))
    db.execute("DELETE FROM activity_updates WHERE activity_id=?", (activity_id,))
    db.execute("DELETE FROM checklist_items WHERE activity_id=?", (activity_id,))
    db.execute("DELETE FROM mentions WHERE activity_id=?", (activity_id,))
    db.execute("DELETE FROM activities WHERE id=?", (activity_id,))
    db.commit()
    flash('Activity deleted.', 'success')
    return redirect(url_for('admin_activities'))


@app.route('/admin/activities/<int:activity_id>/checklist/add', methods=['POST'])
@admin_required
def admin_add_checklist_item(activity_id):
    db = get_db()
    item_text = request.form.get('item_text', '').strip()
    if item_text:
        max_order = db.execute(
            "SELECT COALESCE(MAX(sort_order),0) FROM checklist_items WHERE activity_id=?",
            (activity_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO checklist_items (activity_id, item_text, sort_order) VALUES (?, ?, ?)",
            (activity_id, item_text, max_order + 1)
        )
        db.commit()
    return redirect(url_for('activity_detail', activity_id=activity_id))


# ---------------------------------------------------------------------------
# ADMIN – MENTION / FLAG USERS
# ---------------------------------------------------------------------------

@app.route('/admin/activities/<int:activity_id>/mention', methods=['POST'])
@admin_required
def admin_mention_user(activity_id):
    db = get_db()
    user_id = request.form.get('user_id', type=int)
    message = request.form.get('message', '').strip()
    if user_id and message:
        db.execute(
            "INSERT INTO mentions (activity_id, user_id, message, created_by) VALUES (?, ?, ?, ?)",
            (activity_id, user_id, message, session['user_id'])
        )
        db.commit()
        flash('User has been mentioned/notified.', 'success')
    return redirect(url_for('admin_activities'))


@app.route('/mentions')
@login_required
def my_mentions():
    db = get_db()
    mentions = db.execute("""
        SELECT m.*, a.title AS activity_title, u.full_name AS from_name
        FROM mentions m
        JOIN activities a ON m.activity_id = a.id
        JOIN users u ON m.created_by = u.id
        WHERE m.user_id = ?
        ORDER BY m.created_at DESC
    """, (session['user_id'],)).fetchall()
    db.execute("UPDATE mentions SET is_read = 1 WHERE user_id = ?", (session['user_id'],))
    db.commit()
    return render_template('mentions.html', mentions=mentions)


# ---------------------------------------------------------------------------
# ADMIN – USER MANAGEMENT
# ---------------------------------------------------------------------------

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY role DESC, full_name").fetchall()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/create', methods=['POST'])
@admin_required
def admin_create_user():
    db = get_db()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', 'user')
    shift = request.form.get('shift', 'A')
    engineer_type = request.form.get('engineer_type', 'Process')
    if not username or not password or not full_name:
        flash('All fields are required.', 'warning')
        return redirect(url_for('admin_users'))
    try:
        db.execute(
            "INSERT INTO users (username, password, full_name, role, shift, engineer_type) VALUES (?, ?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), full_name, role, shift, engineer_type)
        )
        db.commit()
        flash(f'User "{full_name}" created.', 'success')
    except sqlite3.IntegrityError:
        flash('Username already exists.', 'danger')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def admin_edit_user(user_id):
    db = get_db()
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', 'user')
    shift = request.form.get('shift', 'A')
    engineer_type = request.form.get('engineer_type', 'Process')
    is_active = 1 if request.form.get('is_active') else 0
    new_password = request.form.get('new_password', '').strip()
    db.execute("UPDATE users SET full_name=?, role=?, shift=?, engineer_type=?, is_active=? WHERE id=?",
               (full_name, role, shift, engineer_type, is_active, user_id))
    if new_password:
        db.execute("UPDATE users SET password=? WHERE id=?",
                   (generate_password_hash(new_password), user_id))
    db.commit()
    flash('User updated.', 'success')
    return redirect(url_for('admin_users'))


# ---------------------------------------------------------------------------
# ADMIN – ANNOUNCEMENTS
# ---------------------------------------------------------------------------

@app.route('/admin/announcements')
@admin_required
def admin_announcements():
    db = get_db()
    all_announcements = db.execute(
        "SELECT a.*, u.full_name AS author_name FROM announcements a "
        "LEFT JOIN users u ON a.created_by = u.id ORDER BY a.created_at DESC"
    ).fetchall()
    return render_template('admin_announcements.html', all_announcements=all_announcements)


@app.route('/admin/announcements/create', methods=['POST'])
@admin_required
def admin_create_announcement():
    db = get_db()
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    priority = request.form.get('priority', 'info')
    expires_at = request.form.get('expires_at', '').strip() or None
    if not title:
        flash('Announcement title is required.', 'warning')
        return redirect(url_for('admin_announcements'))
    db.execute(
        "INSERT INTO announcements (title, content, priority, expires_at, created_by) VALUES (?, ?, ?, ?, ?)",
        (title, content, priority, expires_at, session['user_id'])
    )
    db.commit()
    flash('Announcement created.', 'success')
    return redirect(url_for('admin_announcements'))


@app.route('/admin/announcements/<int:ann_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_announcement(ann_id):
    db = get_db()
    ann = db.execute("SELECT is_active FROM announcements WHERE id=?", (ann_id,)).fetchone()
    if ann:
        new_state = 0 if ann['is_active'] else 1
        db.execute("UPDATE announcements SET is_active=? WHERE id=?", (new_state, ann_id))
        db.commit()
    flash('Announcement updated.', 'success')
    return redirect(url_for('admin_announcements'))


@app.route('/admin/announcements/<int:ann_id>/delete', methods=['POST'])
@admin_required
def admin_delete_announcement(ann_id):
    db = get_db()
    db.execute("DELETE FROM announcements WHERE id=?", (ann_id,))
    db.commit()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('admin_announcements'))


# ---------------------------------------------------------------------------
# ADMIN – SHIFT CALENDAR MANAGEMENT
# ---------------------------------------------------------------------------

# 4C2S rotation: 28-day cycle for each crew
# Pattern per crew: D=Day, N=Night, O=Off
# Classic 4-crew 2-shift continental rotation
ROTATION_CYCLE = {
    'A': ['D','D','D','D','O','O','O','N','N','N','N','O','O','O',
          'D','D','D','D','O','O','O','N','N','N','N','O','O','O'],
    'B': ['O','O','O','N','N','N','N','O','O','O','D','D','D','D',
          'O','O','O','N','N','N','N','O','O','O','D','D','D','D'],
    'C': ['N','N','N','N','O','O','O','D','D','D','D','O','O','O',
          'N','N','N','N','O','O','O','D','D','D','D','O','O','O'],
    'D': ['O','O','O','D','D','D','D','O','O','O','N','N','N','N',
          'O','O','O','D','D','D','D','O','O','O','N','N','N','N'],
}
# Epoch: Jan 5, 2026 (Monday) is day 0 of the cycle
ROTATION_EPOCH = date(2026, 1, 5)


def get_shift_for_date(d, crew):
    """Return 'D', 'N', or 'O' for a given date and crew."""
    delta = (d - ROTATION_EPOCH).days % 28
    return ROTATION_CYCLE[crew][delta]


def get_calendar_month(year, month, db, include_users=False):
    """Build calendar data for a given month."""
    cal = calendar.Calendar(firstweekday=0)  # Monday start
    weeks = cal.monthdatescalendar(year, month)

    # Fetch holidays for this month range
    first_day = weeks[0][0]
    last_day = weeks[-1][-1]
    holidays = {}
    for h in db.execute(
        "SELECT date, name FROM public_holidays WHERE date BETWEEN ? AND ?",
        (first_day.isoformat(), last_day.isoformat())
    ).fetchall():
        holidays[h['date']] = h['name']

    # Fetch overrides for this month range
    overrides = {}
    for o in db.execute(
        "SELECT date, crew, override_type, note FROM shift_calendar_overrides WHERE date BETWEEN ? AND ?",
        (first_day.isoformat(), last_day.isoformat())
    ).fetchall():
        key = (o['date'], o['crew'])
        overrides[key] = {'type': o['override_type'], 'note': o['note']}

    # Fetch user schedule overrides for this month range
    user_overrides = {}  # key = date -> list of {user_id, full_name, type, note}
    for uo in db.execute(
        "SELECT uso.date, uso.user_id, uso.type, uso.note, uso.id, u.full_name "
        "FROM user_schedule_overrides uso JOIN users u ON uso.user_id = u.id "
        "WHERE uso.date BETWEEN ? AND ? ORDER BY u.full_name",
        (first_day.isoformat(), last_day.isoformat())
    ).fetchall():
        if uo['date'] not in user_overrides:
            user_overrides[uo['date']] = []
        user_overrides[uo['date']].append({
            'id': uo['id'], 'user_id': uo['user_id'],
            'full_name': uo['full_name'], 'type': uo['type'], 'note': uo['note'] or ''
        })

    # Optionally fetch crew user lists for tooltips
    crew_users = {}
    if include_users:
        for u in db.execute(
            "SELECT id, full_name, shift, engineer_type FROM users WHERE role != 'admin' ORDER BY full_name"
        ).fetchall():
            crew = u['shift']
            if crew not in crew_users:
                crew_users[crew] = []
            crew_users[crew].append({
                'id': u['id'], 'name': u['full_name'],
                'eng_type': u['engineer_type'] or 'Process'
            })

    result_weeks = []
    for week in weeks:
        week_data = []
        for day in week:
            crews = {}
            for crew in ['A', 'B', 'C', 'D']:
                override_key = (day.isoformat(), crew)
                if override_key in overrides:
                    crews[crew] = overrides[override_key]['type']  # 'REP', 'OFF', 'D', 'N'
                else:
                    crews[crew] = get_shift_for_date(day, crew)
            day_data = {
                'date': day.isoformat(),
                'day': day.day,
                'in_month': day.month == month,
                'is_today': day == date.today(),
                'weekday': day.strftime('%a'),
                'holiday': holidays.get(day.isoformat()),
                'crews': crews,
                'user_overrides': user_overrides.get(day.isoformat(), []),
            }
            week_data.append(day_data)
        # Calculate work week number (ISO week)
        ww = week[0].isocalendar()[1]
        result_weeks.append({'ww': ww, 'days': week_data})

    return result_weeks, crew_users


@app.route('/admin/calendar')
@admin_required
def admin_calendar():
    db = get_db()
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)
    cal_data, crew_users = get_calendar_month(year, month, db, include_users=True)
    holidays = db.execute("SELECT * FROM public_holidays ORDER BY date").fetchall()
    overrides = db.execute(
        "SELECT o.*, u.full_name AS author_name FROM shift_calendar_overrides o "
        "LEFT JOIN users u ON o.created_by = u.id ORDER BY o.date DESC LIMIT 50"
    ).fetchall()
    all_users = db.execute(
        "SELECT id, full_name, shift, engineer_type FROM users WHERE role != 'admin' ORDER BY full_name"
    ).fetchall()
    return render_template('admin_calendar.html', cal_data=cal_data, year=year, month=month,
                           holidays=holidays, overrides=overrides, crew_users=crew_users,
                           all_users=all_users)


@app.route('/admin/calendar/holiday/add', methods=['POST'])
@admin_required
def admin_add_holiday():
    db = get_db()
    hdate = request.form.get('date', '').strip()
    hname = request.form.get('name', '').strip()
    if hdate and hname:
        try:
            db.execute("INSERT INTO public_holidays (date, name, created_by) VALUES (?, ?, ?)",
                       (hdate, hname, session['user_id']))
            db.commit()
            flash(f'Holiday "{hname}" added.', 'success')
        except sqlite3.IntegrityError:
            flash('Holiday for that date already exists.', 'warning')
    return redirect(url_for('admin_calendar'))


@app.route('/admin/calendar/holiday/<int:hid>/delete', methods=['POST'])
@admin_required
def admin_delete_holiday(hid):
    db = get_db()
    db.execute("DELETE FROM public_holidays WHERE id=?", (hid,))
    db.commit()
    flash('Holiday removed.', 'success')
    return redirect(url_for('admin_calendar'))


@app.route('/admin/calendar/override/add', methods=['POST'])
@admin_required
def admin_add_override():
    db = get_db()
    odate = request.form.get('date', '').strip()
    crew = request.form.get('crew', '').strip().upper()
    override_type = request.form.get('override_type', '').strip()
    note = request.form.get('note', '').strip()
    if odate and crew and override_type:
        db.execute(
            "INSERT INTO shift_calendar_overrides (date, crew, override_type, note, created_by) VALUES (?, ?, ?, ?, ?)",
            (odate, crew, override_type, note, session['user_id'])
        )
        db.commit()
        flash(f'Override ({override_type}) for Crew {crew} on {odate} added.', 'success')
    return redirect(url_for('admin_calendar'))


@app.route('/admin/calendar/override/<int:oid>/delete', methods=['POST'])
@admin_required
def admin_delete_override(oid):
    db = get_db()
    db.execute("DELETE FROM shift_calendar_overrides WHERE id=?", (oid,))
    db.commit()
    flash('Override removed.', 'success')
    return redirect(url_for('admin_calendar'))


@app.route('/admin/calendar/user-override/add', methods=['POST'])
@admin_required
def admin_add_user_override():
    """Add a user-level schedule override (OT, LEAVE, OFF, SWAP)."""
    db = get_db()
    odate = request.form.get('date', '').strip()
    user_id = request.form.get('user_id', type=int)
    override_type = request.form.get('type', '').strip()
    note = request.form.get('note', '').strip()
    if odate and user_id and override_type:
        # Prevent duplicate for same user+date
        existing = db.execute(
            "SELECT id FROM user_schedule_overrides WHERE date=? AND user_id=?",
            (odate, user_id)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE user_schedule_overrides SET type=?, note=?, created_by=? WHERE id=?",
                (override_type, note, session['user_id'], existing['id'])
            )
        else:
            db.execute(
                "INSERT INTO user_schedule_overrides (date, user_id, type, note, created_by) VALUES (?, ?, ?, ?, ?)",
                (odate, user_id, override_type, note, session['user_id'])
            )
        db.commit()
        user = db.execute("SELECT full_name FROM users WHERE id=?", (user_id,)).fetchone()
        uname = user['full_name'] if user else f'User #{user_id}'
        flash(f'{override_type} for {uname} on {odate} saved.', 'success')
    return redirect(url_for('admin_calendar'))


@app.route('/admin/calendar/user-override/<int:oid>/delete', methods=['POST'])
@admin_required
def admin_delete_user_override(oid):
    """Remove a user-level schedule override."""
    db = get_db()
    db.execute("DELETE FROM user_schedule_overrides WHERE id=?", (oid,))
    db.commit()
    flash('User override removed.', 'success')
    return redirect(url_for('admin_calendar'))


@app.route('/api/shift-calendar')
@login_required
def api_shift_calendar():
    """JSON API for calendar month navigation on dashboard."""
    db = get_db()
    year = request.args.get('year', type=int, default=datetime.now().year)
    month = request.args.get('month', type=int, default=datetime.now().month)
    cal_data, _ = get_calendar_month(year, month, db)
    month_name = calendar.month_name[month]
    return jsonify({'weeks': cal_data, 'year': year, 'month': month, 'month_name': month_name})


# ---------------------------------------------------------------------------
# SHIFT REPORT / EMAIL
# ---------------------------------------------------------------------------

@app.route('/generate-report')
@login_required
def generate_report():
    db = get_db()
    shift = current_shift()
    today = datetime.now().strftime('%Y-%m-%d')
    updates = db.execute("""
        SELECT au.*, a.title AS activity_title, a.customer, a.device,
               a.progress_type, a.progress_total, a.progress_current, a.id AS act_id,
               u.full_name AS user_name
        FROM activity_updates au
        JOIN activities a ON au.activity_id = a.id
        JOIN users u ON au.user_id = u.id
        WHERE DATE(au.created_at) = ? AND au.shift = ?
        ORDER BY au.created_at DESC
    """, (today, shift)).fetchall()

    # Also get activity-level progress for all active activities
    all_activities = db.execute("SELECT * FROM activities WHERE status='active' ORDER BY title").fetchall()
    activities_progress = []
    for a in all_activities:
        pct = calc_progress(a, db)
        activities_progress.append({'row': a, 'progress': pct})

    return render_template('report.html', updates=updates, shift=shift, today=today,
                           activities_progress=activities_progress)


@app.route('/send-report', methods=['POST'])
@admin_required
def send_report():
    db = get_db()
    shift = current_shift()
    today = datetime.now().strftime('%Y-%m-%d')
    recipients = request.form.get('recipients', '').strip()
    subject = request.form.get('subject', f'Wire Bond Activity Update - Shift {shift} - {today}')
    updates = db.execute("""
        SELECT au.*, a.title AS activity_title, a.customer, a.device,
               a.progress_type, a.progress_total, a.progress_current, a.id AS act_id,
               u.full_name AS user_name
        FROM activity_updates au
        JOIN activities a ON au.activity_id = a.id
        JOIN users u ON au.user_id = u.id
        WHERE DATE(au.created_at) = ? AND au.shift = ?
        ORDER BY au.created_at DESC
    """, (today, shift)).fetchall()

    all_activities = db.execute("SELECT * FROM activities WHERE status='active'").fetchall()
    activity_progress = {}
    for a in all_activities:
        activity_progress[a['id']] = calc_progress(a, db)

    html_body = build_email_html(updates, shift, today, session.get('full_name', 'Unknown'),
                                  all_activities, activity_progress)
    success = False
    error_msg = ''
    try:
        success = send_via_lotus_notes(recipients, subject, html_body)
    except Exception as e:
        error_msg = str(e)

    db.execute(
        "INSERT INTO email_log (shift, sent_by, subject, body_html, status) VALUES (?, ?, ?, ?, ?)",
        (shift, session['user_id'], subject, html_body, 'sent' if success else f'failed: {error_msg}')
    )
    db.commit()

    if success:
        flash('Report sent via Lotus Notes!', 'success')
    else:
        flash(f'Could not send via Lotus Notes: {error_msg}. You can copy the HTML manually.', 'warning')
    return redirect(url_for('generate_report'))


def _progress_bar_html(pct):
    """Build an inline-HTML progress bar for emails."""
    if pct is None:
        return ''
    color = '#27AE60' if pct >= 75 else '#F39C12' if pct >= 40 else '#E74C3C'
    return (
        f'<div style="display:inline-flex;align-items:center;gap:6px;">'
        f'<div style="width:80px;height:10px;background:#e0e0e0;border-radius:5px;overflow:hidden;">'
        f'<div style="width:{pct}%;height:100%;background:{color};border-radius:5px;"></div></div>'
        f'<span style="font-size:11px;font-weight:700;color:{color};">{pct:.0f}%</span></div>'
    )


def build_email_html(updates, shift, today, sender_name, all_activities=None, activity_progress=None):
    """Build a nicely formatted HTML email body with progress."""
    update_rows = ''
    for u in updates:
        pct = activity_progress.get(u['act_id']) if activity_progress else None
        bar = _progress_bar_html(pct)
        update_rows += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">{u['activity_title']}</td>
            <td style="padding:8px;border:1px solid #ddd;">{u['customer'] or '-'}</td>
            <td style="padding:8px;border:1px solid #ddd;">{u['device'] or '-'}</td>
            <td style="padding:8px;border:1px solid #ddd;">{u['update_text']}</td>
            <td style="padding:8px;border:1px solid #ddd;">{bar}</td>
            <td style="padding:8px;border:1px solid #ddd;">{u['user_name']}</td>
            <td style="padding:8px;border:1px solid #ddd;">{u['created_at']}</td>
        </tr>"""

    # Progress summary for all active activities
    progress_rows = ''
    if all_activities and activity_progress:
        for a in all_activities:
            pct = activity_progress.get(a['id'])
            if pct is not None:
                bar = _progress_bar_html(pct)
                progress_rows += f"""
                <tr>
                    <td style="padding:6px 8px;border:1px solid #ddd;">{a['title']}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;">{bar}</td>
                </tr>"""

    progress_section = ''
    if progress_rows:
        progress_section = f"""
        <div style="margin-top:16px;">
            <h3 style="font-size:14px;color:#1B4F72;margin-bottom:8px;">Activity Progress Summary</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead><tr style="background:#f0f3f7;">
                    <th style="padding:6px 8px;border:1px solid #ddd;text-align:left;">Activity</th>
                    <th style="padding:6px 8px;border:1px solid #ddd;text-align:left;">Progress</th>
                </tr></thead>
                <tbody>{progress_rows}</tbody>
            </table>
        </div>"""

    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:0 auto;">
        <div style="background:#1B4F72;color:white;padding:16px 24px;border-radius:6px 6px 0 0;">
            <h2 style="margin:0;">Wire Bond Group - Activity Flow System</h2>
            <p style="margin:4px 0 0;opacity:0.9;">Shift {shift} ({current_time_slot()}) | {today} | Reported by: {sender_name}</p>
        </div>
        <div style="padding:16px 24px;border:1px solid #ddd;border-top:none;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                    <tr style="background:#f0f3f7;">
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Activity</th>
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Customer</th>
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Device</th>
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Update</th>
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Progress</th>
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">By</th>
                        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Time</th>
                    </tr>
                </thead>
                <tbody>
                    {update_rows if update_rows else '<tr><td colspan="7" style="padding:12px;text-align:center;color:#999;">No updates for this shift.</td></tr>'}
                </tbody>
            </table>
            {progress_section}
        </div>
        <div style="background:#f0f3f7;padding:12px 24px;border:1px solid #ddd;border-top:none;border-radius:0 0 6px 6px;font-size:12px;color:#666;">
            Wire Bond Group Activity Flow System &mdash; Auto-generated shift report
        </div>
    </div>"""


def send_via_lotus_notes(recipients, subject, html_body):
    try:
        import win32com.client
    except ImportError:
        raise RuntimeError("pywin32 not installed. Run: pip install pywin32")
    try:
        ns = win32com.client.Dispatch("Lotus.NotesSession")
        ns.Initialize("")
        ndb = ns.GetDatabase("", "")
        if not ndb.IsOpen:
            ndb.OpenMail()
        doc = ndb.CreateDocument()
        doc.ReplaceItemValue("Form", "Memo")
        doc.ReplaceItemValue("Subject", subject)
        doc.ReplaceItemValue("SendTo", [r.strip() for r in recipients.split(',') if r.strip()])
        body = doc.CreateRichTextItem("Body")
        body.AppendText(html_body)
        doc.Send(False)
        return True
    except Exception as e:
        raise RuntimeError(f"Lotus Notes error: {e}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_PHOTOS'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FILES'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    init_db()
    print("\n" + "=" * 60)
    print("  Wire Bond Group - Activity Flow System")
    print("  Local:   http://127.0.0.1:5000")
    print("  Network: http://0.0.0.0:5000  (accessible on LAN)")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
