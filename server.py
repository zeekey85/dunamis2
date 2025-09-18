import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (Flask, request, jsonify, send_from_directory, redirect,
                   url_for, render_template)
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
import datetime
import shutil
import logging
from logging.handlers import TimedRotatingFileHandler
from functools import wraps
import pandas as pd
import subprocess
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__, template_folder='web')
app.secret_key = b'a_much_more_secure_secret_key_please_change'
CORS(app)

# --- DIRECTORY AND DATABASE PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'api', 'users.db')
WEB_DIR = os.path.join(BASE_DIR, 'web')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
PLANNED_DIR = os.path.join(BASE_DIR, 'planned_workouts')
INPROGRESS_DIR = os.path.join(BASE_DIR, 'inprogress_workouts')
FINISHED_DIR = os.path.join(BASE_DIR, 'finished_workouts')
API_DIR = os.path.join(BASE_DIR, 'api')
EMAILS_PATH = os.path.join(API_DIR, 'emails.csv')

# --- LOGGING SETUP ---
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
log_file = os.path.join(BASE_DIR, 'dunamis_app.log')
handler = TimedRotatingFileHandler(log_file, when='midnight', interval=1, backupCount=7)
handler.setFormatter(log_formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Dunamis App starting up...')

for directory in [WEB_DIR, PLANNED_DIR, INPROGRESS_DIR, FINISHED_DIR, API_DIR, ASSETS_DIR]:
    os.makedirs(directory, exist_ok=True)

# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    if user_id is not None and int(user_id) == 1:
        app.logger.info(f"load_user: Successfully loaded coach user (ID: {user_id}) from session.")
        return User(id=1, username='coach', role='coach')
    app.logger.warning(f"load_user: Attempted to load an invalid user_id from session: {user_id}")
    return None

@login_manager.unauthorized_handler
def unauthorized_callback():
    app.logger.warning(f"Unauthorized access attempt to path: {request.path}")
    if request.path.startswith('/api/'):
        return jsonify(status='error', message='Authentication required'), 401
    return redirect(url_for('login'))

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'athlete'
            );
        ''')
        cursor.execute("SELECT * FROM users WHERE username = ?", ('coach',))
        if cursor.fetchone() is None:
            hashed_password = generate_password_hash('get$trong@dunamis')
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('coach', hashed_password, 'coach')
            )
init_db()

# --- DECORATORS ---
def coach_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'coach':
            return jsonify(status='error', message='Coach access required'), 403
        return f(*args, **kwargs)
    return decorated_function

# --- EMAIL FUNCTIONS ---
def get_athlete_email(athlete_name):
    try:
        with open(EMAILS_PATH, mode='r') as infile:
            reader = csv.reader(infile)
            next(reader, None)
            for row in reader:
                if row[0].lower() == athlete_name.lower():
                    return row[1]
    except FileNotFoundError:
        app.logger.error(f"Email file not found at {EMAILS_PATH}")
    except Exception as e:
        app.logger.error(f"Error reading email file: {e}")
    return None

def send_email_with_python(recipient_email, subject, body, attachment_path):
    """Sends an email using Python's smtplib, reading credentials from environment variables."""
    sender_email = os.environ.get('EMAIL_USER')
    sender_password = os.environ.get('EMAIL_PASS')
    smtp_server = os.environ.get('EMAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('EMAIL_PORT', 587))

    if not all([sender_email, sender_password]):
        app.logger.error("Email credentials (EMAIL_USER, EMAIL_PASS) are not set in environment variables. Cannot send email.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(attachment_path)}")
        msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        app.logger.info(f"Successfully sent workout email to {recipient_email} via Python smtplib.")
    except Exception as e:
        app.logger.error(f"Failed to send email to {recipient_email} via Python smtplib. Error: {e}")


# --- USER MANAGEMENT & CORE ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'coach' and password == 'get$trong@dunamis':
            user = User(id=1, username='coach', role='coach')
            login_user(user, remember=True)
            app.logger.info("Coach user logged in successfully. Session created.")
            return redirect(url_for('root'))
        else:
            app.logger.warning(f"Failed login attempt for username: {username}")
            return 'Invalid credentials. Please try again.', 401
    return render_template('login.html')

# ... (other routes like /register, /logout, /, static files remain the same) ...

# --- API ENDPOINTS ---
# ... (/api/get_current_user, /api/get_athletes, etc. remain the same) ...

@app.route('/api/complete_workout', methods=['POST'])
@login_required
def complete_workout():
    data = request.get_json()
    plan_filename = data.get('plan_filename')
    tracked_filename = data.get('tracked_filename')
    csv_content = data.get('csv_content')

    if current_user.role != 'coach' and not tracked_filename.startswith(current_user.username + '_'):
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    
    finished_path = os.path.join(FINISHED_DIR, tracked_filename)
    with open(finished_path, 'w', newline='', encoding='utf-8') as f:
        f.write(csv_content)
    
    plan_path = os.path.join(PLANNED_DIR, plan_filename)
    if os.path.exists(plan_path):
        os.remove(plan_path)

    inprogress_path = os.path.join(INPROGRESS_DIR, tracked_filename)
    if os.path.exists(inprogress_path):
        os.remove(inprogress_path)
    
    app.logger.info(f"Workout '{tracked_filename}' completed by user {current_user.username}")
    
    # --- NEW EMAIL LOGIC ---
    athlete_name = tracked_filename.split('_')[0]
    recipient = get_athlete_email(athlete_name)
    if recipient:
        subject = f"Workout Completed: {plan_filename.replace('.csv', '').replace('_', ' ')}"
        body = f"Great work, {athlete_name}!\n\nYour workout has been completed. The full details are attached.\n\n- Dunamis Training"
        send_email_with_python(recipient, subject, body, finished_path) # <-- Use the new function
    else:
        app.logger.warning(f"Could not find email for athlete '{athlete_name}'. Skipping email notification.")

    return jsonify({"status": "success", "message": "Workout completed."})

# ... (rest of the API endpoints remain the same) ...
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

