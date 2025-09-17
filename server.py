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
    """Loads user from session. Simplified for hardcoded 'coach' user."""
    # Since login is hardcoded for the coach (ID 1), this is the only case we need to handle.
    if user_id is not None and int(user_id) == 1:
        app.logger.info(f"load_user: Successfully loaded coach user (ID: {user_id}) from session.")
        return User(id=1, username='coach', role='coach')
    
    # If the user_id is anything else, they are not a valid user in this hardcoded setup.
    app.logger.warning(f"load_user: Attempted to load an invalid user_id from session: {user_id}")
    return None

@login_manager.unauthorized_handler
def unauthorized_callback():
    app.logger.warning(f"Unauthorized access attempt to path: {request.path}")
    if request.path.startswith('/api/'):
        return jsonify(status='error', message='Authentication required'), 401
    return redirect(url_for('login'))

def init_db():
    # This function is kept for potential future use but is not critical for the current hardcoded login.
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
            next(reader, None) # Skip header
            for row in reader:
                if row[0].lower() == athlete_name.lower():
                    return row[1]
    except FileNotFoundError:
        app.logger.error(f"Email file not found at {EMAILS_PATH}")
    except Exception as e:
        app.logger.error(f"Error reading email file: {e}")
    return None

def send_email_notification(recipient_email, subject, body, attachment_path):
    try:
        command = f'echo "{body}" | mail -s "{subject}" -A "{attachment_path}" {recipient_email}'
        subprocess.run(command, shell=True, check=True)
        app.logger.info(f"Successfully sent workout email to {recipient_email}")
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Failed to send email to {recipient_email}. Error: {e}")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during email sending: {e}")

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def root():
    return redirect(url_for('send_html', path='index.html'))

# --- STATIC FILE SERVING ---
@app.route('/assets/<path:filename>')
def serve_asset(filename):
    return send_from_directory(ASSETS_DIR, filename)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(ASSETS_DIR, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/<path:path>')
@login_required
def send_html(path):
    return send_from_directory(WEB_DIR, path)

# --- API ENDPOINTS ---

@app.route('/api/test_email', methods=['GET'])
@coach_required
def test_email():
    recipient = request.args.get('recipient')
    if not recipient:
        return jsonify({"status": "error", "message": "Recipient email address is required as a query parameter (e.g., ?recipient=test@example.com)."}), 400
    app.logger.info(f"Initiating test email to {recipient}")
    subject = "Dunamis App: Test Email"
    body = "This is a test email sent from the Dunamis workout application to verify the email configuration."
    test_attachment_path = os.path.join(BASE_DIR, 'test_attachment.txt')
    with open(test_attachment_path, 'w') as f:
        f.write('This is a test attachment file.')
    try:
        command = f'echo "{body}" | mail -v -s "{subject}" -A "{test_attachment_path}" {recipient}'
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        os.remove(test_attachment_path)
        app.logger.info(f"Test email command executed successfully. STDOUT: {result.stdout}")
        return jsonify({"status": "success", "message": "Test email command executed. Check the recipient's inbox and the server logs.", "stdout": result.stdout, "stderr": result.stderr})
    except subprocess.CalledProcessError as e:
        if os.path.exists(test_attachment_path): os.remove(test_attachment_path)
        app.logger.error(f"Failed to send test email to {recipient}. Stderr: {e.stderr}")
        return jsonify({"status": "error", "message": "Failed to execute the mail command. Check logs for details.", "stdout": e.stdout, "stderr": e.stderr}), 500
    except Exception as e:
        if os.path.exists(test_attachment_path): os.remove(test_attachment_path)
        app.logger.error(f"An unexpected error occurred during test email sending: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/get_current_user', methods=['GET'])
@login_required
def get_current_user():
    return jsonify({"status": "success", "username": current_user.username, "role": current_user.role})

# ... The rest of the API endpoints remain unchanged ...
def filter_files_by_user(files, username=None):
    user_to_check = username or current_user.username
    return [f for f in files if f.lower().startswith(user_to_check.lower() + '_')]

@app.route('/api/get_athletes', methods=['GET'])
@coach_required
def get_athletes():
    try:
        all_files = os.listdir(PLANNED_DIR) + os.listdir(FINISHED_DIR)
        athletes = set()
        for f in all_files:
            if f.endswith('.csv'):
                username = f.split('_')[0]
                if username and username.lower() != 'coach':
                    athletes.add(username)
        return jsonify({"status": "success", "athletes": sorted(list(athletes))})
    except Exception as e:
        app.logger.error(f"Could not get athletes: {e}")
        return jsonify({"status": "error", "message": "Could not retrieve athlete list."}), 500

@app.route('/api/list_workouts_for_tracker', methods=['GET'])
@login_required
def list_workouts_for_tracker():
    username_to_view = request.args.get('user', current_user.username)
    if current_user.role != 'coach' and username_to_view != current_user.username:
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    planned_files = [f for f in os.listdir(PLANNED_DIR) if f.endswith('.csv')]
    in_progress_files = [f for f in os.listdir(INPROGRESS_DIR) if f.endswith('_tracked.csv')]
    user_planned = filter_files_by_user(planned_files, username_to_view)
    user_tracked = filter_files_by_user(in_progress_files, username_to_view)
    plans_in_progress_base = {f.replace('_tracked.csv', '.csv') for f in user_tracked}
    active_plans = [p for p in user_planned if p not in plans_in_progress_base]
    return jsonify({
        "status": "success", 
        "plans": sorted(active_plans, reverse=True), 
        "tracked": sorted(user_tracked, reverse=True)
    })

@app.route('/api/mesocycle_view', methods=['GET'])
@login_required
def mesocycle_view():
    username_to_view = request.args.get('user', current_user.username)
    if current_user.role != 'coach' and username_to_view != current_user.username:
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    finished_files = filter_files_by_user([f for f in os.listdir(FINISHED_DIR) if f.endswith('_tracked.csv')], username_to_view)
    planned_files = filter_files_by_user([f for f in os.listdir(PLANNED_DIR) if f.endswith('.csv')], username_to_view)
    in_progress_bases = {f.replace('_tracked.csv', '.csv') for f in os.listdir(INPROGRESS_DIR)}
    active_planned_files = [p for p in planned_files if p not in in_progress_bases]
    def get_date(f):
        try: return datetime.datetime.strptime(f.split('_')[-1].replace('.csv',''), '%Y-%m-%d')
        except: return datetime.datetime.max
    finished_files.sort(key=get_date, reverse=True)
    active_planned_files.sort(key=get_date)
    return jsonify({"status": "success", "data": {"completed": finished_files[:5], "planned": active_planned_files[:6]}})

@app.route('/api/get_analysis', methods=['GET'])
@login_required
def get_analysis():
    username_to_view = request.args.get('user', current_user.username)
    if current_user.role != 'coach' and username_to_view != current_user.username:
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    user_files_fullpaths = [os.path.join(FINISHED_DIR, f) for f in filter_files_by_user([f for f in os.listdir(FINISHED_DIR) if f.endswith('_tracked.csv')], username_to_view)]
    results = analyze_workout_data(user_files_fullpaths)
    return jsonify({"status": "success", "analysis": results})

def analyze_workout_data(file_list):
    if not file_list: return {}
    df_list = []
    for i, file_path in enumerate(sorted(file_list)):
        try:
            df = pd.read_csv(file_path)
            parts = os.path.basename(file_path).replace('_tracked.csv', '').split('_')
            df['date'] = pd.to_datetime(parts[-1])
            df_list.append(df)
        except Exception as e:
            app.logger.error(f"Could not process file {file_path}: {e}")
    if not df_list: return {}
    full_df = pd.concat(df_list, ignore_index=True)
    full_df['Actual Weight'] = pd.to_numeric(full_df.get('Actual Weight (lb)'), errors='coerce').fillna(0)
    full_df['Actual Reps'] = pd.to_numeric(full_df.get('Actual Reps'), errors='coerce').fillna(0)
    full_df['volume'] = full_df['Actual Reps'] * full_df['Actual Weight']
    agg_df = full_df.groupby(['Exercise', 'date']).agg(max_weight=('Actual Weight', 'max'), total_volume=('volume', 'sum')).reset_index()
    return {name: g.sort_values('date').to_dict('list') for name, g in agg_df.groupby('Exercise')}

def get_latest_exercise_performance(username, exercise_name):
    user_files = filter_files_by_user([f for f in os.listdir(FINISHED_DIR) if f.endswith('_tracked.csv')], username)
    def get_date_from_filename(f):
        try: return datetime.datetime.strptime(f.split('_')[-1].replace('_tracked.csv',''), '%Y-%m-%d')
        except: return datetime.datetime.min
    user_files.sort(key=get_date_from_filename, reverse=True)
    for filename in user_files:
        try:
            df = pd.read_csv(os.path.join(FINISHED_DIR, filename))
            if exercise_name.lower() in df['Exercise'].str.lower().values:
                exercise_df = df[df['Exercise'].str.lower() == exercise_name.lower()]
                if 'Actual Reps' in exercise_df.columns and 'Actual Weight (lb)' in exercise_df.columns:
                    exercise_df['Actual Reps'] = pd.to_numeric(exercise_df['Actual Reps'], errors='coerce').fillna(0)
                    exercise_df['Actual Weight (lb)'] = pd.to_numeric(exercise_df['Actual Weight (lb)'], errors='coerce').fillna(0)
                    history = exercise_df[['Actual Reps', 'Actual Weight (lb)']].to_dict('records')
                    return {"date": get_date_from_filename(filename).strftime('%Y-%m-%d'), "sets": history}
        except Exception as e:
            app.logger.error(f"Error processing {filename} for history: {e}")
    return None

@app.route('/api/get_exercise_history', methods=['GET'])
@login_required
def get_exercise_history():
    username = request.args.get('user')
    exercise = request.args.get('exercise')
    if not username or not exercise:
        return jsonify({"status": "error", "message": "User and exercise parameters are required."}), 400
    if current_user.role != 'coach' and username != current_user.username:
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    history_data = get_latest_exercise_performance(username, exercise)
    if history_data:
        return jsonify({"status": "success", "history": history_data})
    else:
        return jsonify({"status": "success", "history": None, "message": "No prior history found."})

@app.route('/api/save_plan', methods=['POST'])
@login_required
def save_plan():
    data = request.get_json()
    filename = data.get('filename')
    if current_user.role != 'coach' and not filename.startswith(current_user.username + '_'):
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    with open(os.path.join(PLANNED_DIR, filename), 'w', newline='', encoding='utf-8') as f:
        f.write(data.get('csv_content'))
    app.logger.info(f"Plan '{filename}' saved for user {current_user.username}")
    return jsonify({"status": "success", "message": f"Plan '{filename}' saved."})

@app.route('/api/save_progress', methods=['POST'])
@login_required
def save_progress():
    data = request.get_json()
    filename = data.get('filename')
    if current_user.role != 'coach' and not filename.startswith(current_user.username + '_'):
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    with open(os.path.join(INPROGRESS_DIR, filename), 'w', newline='', encoding='utf-8') as f:
        f.write(data.get('csv_content'))
    app.logger.info(f"Progress saved for workout '{filename}' by user {current_user.username}")
    return jsonify({"status": "success", "message": "Progress saved."})

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
    
    athlete_name = tracked_filename.split('_')[0]
    recipient = get_athlete_email(athlete_name)
    if recipient:
        subject = f"Workout Completed: {plan_filename.replace('.csv', '').replace('_', ' ')}"
        body = f"Great work, {athlete_name}!\n\nYour workout has been completed. The full details are attached.\n\n- Dunamis Training"
        send_email_notification(recipient, subject, body, finished_path)
    else:
        app.logger.warning(f"Could not find email for athlete '{athlete_name}'. Skipping email notification.")

    return jsonify({"status": "success", "message": "Workout completed."})

@app.route('/api/get_exercises', methods=['GET'])
@login_required
def get_exercises():
    exercises_path = os.path.join(API_DIR, 'exercises.csv')
    try:
        df = pd.read_csv(exercises_path)
        return jsonify({"status": "success", "exercises": df['Exercise'].tolist()})
    except Exception as e:
        app.logger.error(f"Could not read exercises file: {e}")
        return jsonify({"status": "error", "message": "Could not read exercises."}), 500

@app.route('/api/add_exercise', methods=['POST'])
@coach_required
def add_exercise():
    data = request.get_json()
    new_exercise = data.get('exercise', '').strip()
    if not new_exercise:
        return jsonify({"status": "error", "message": "Exercise name cannot be empty."}), 400
    
    exercises_path = os.path.join(API_DIR, 'exercises.csv')
    try:
        df = pd.read_csv(exercises_path) if os.path.exists(exercises_path) else pd.DataFrame(columns=['Exercise'])
        if new_exercise.lower() in df['Exercise'].str.lower().values:
            return jsonify({"status": "error", "message": f"Exercise '{new_exercise}' already exists."}), 409
        
        new_df = pd.concat([df, pd.DataFrame([{'Exercise': new_exercise}])], ignore_index=True)
        new_df.sort_values('Exercise', inplace=True)
        new_df.to_csv(exercises_path, index=False)
        app.logger.info(f"New exercise '{new_exercise}' added by {current_user.username}")
        return jsonify({"status": "success", "message": f"Exercise '{new_exercise}' added."}), 201
    except Exception as e:
        app.logger.error(f"Error adding exercise: {e}")
        return jsonify({"status": "error", "message": "Could not add exercise."}), 500

@app.route('/api/get_workout', methods=['GET'])
@login_required
def get_workout_file():
    filename, file_type = request.args.get('filename'), request.args.get('type')
    if current_user.role != 'coach' and not filename.startswith(current_user.username + '_'):
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    dir_map = {'plan': PLANNED_DIR, 'tracked': INPROGRESS_DIR, 'finished': FINISHED_DIR}
    if not dir_map.get(file_type): return jsonify({"status": "error", "message": "Invalid request type."}), 400
    try:
        return send_from_directory(dir_map.get(file_type), filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found."}), 404

@app.route('/api/list_templates', methods=['GET'])
@login_required
def list_templates():
    username_to_view = request.args.get('user', current_user.username)
    if current_user.role != 'coach' and username_to_view != current_user.username:
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    
    finished_files = filter_files_by_user([f for f in os.listdir(FINISHED_DIR) if f.endswith('_tracked.csv')], username_to_view)
    
    templates = [{'filename': f, 'type': 'finished'} for f in finished_files]
    templates.sort(key=lambda x: x['filename'], reverse=True)
    
    return jsonify({"status": "success", "templates": templates})

@app.route('/api/delete_plan', methods=['POST'])
@login_required
def delete_plan():
    filename = request.json.get('filename')
    if current_user.role != 'coach' and not filename.startswith(current_user.username + '_'):
        return jsonify({"status": "error", "message": "Permission denied."}), 403
        
    file_path = os.path.join(PLANNED_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        app.logger.info(f"Plan '{filename}' deleted by {current_user.username}")
        return jsonify({"status": "success", "message": f"Plan '{filename}' deleted."})
    return jsonify({"status": "error", "message": "Plan not found."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

