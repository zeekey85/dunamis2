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
from functools import wraps
import pandas as pd

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
    if int(user_id) == 1:
        return User(id=1, username='coach', role='coach')
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            user_data = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user_data:
            return User(id=user_data['id'], username=user_data['username'], role=user_data['role'])
    except sqlite3.Error as e:
        app.logger.error(f"Database error in load_user: {e}")
    return None

@login_manager.unauthorized_handler
def unauthorized_callback():
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

# --- USER MANAGEMENT & CORE ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'coach' and password == 'get$trong@dunamis':
            user = User(id=1, username='coach', role='coach')
            login_user(user, remember=True)
            return redirect(url_for('root'))
        else:
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
@app.route('/api/get_current_user', methods=['GET'])
@login_required
def get_current_user():
    return jsonify({"status": "success", "username": current_user.username, "role": current_user.role})

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

def filter_files_by_user(files, username=None):
    user_to_check = username or current_user.username
    return [f for f in files if f.lower().startswith(user_to_check.lower() + '_')]

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
    return jsonify({"status": "success", "message": "Progress saved."})

@app.route('/api/complete_workout', methods=['POST'])
@login_required
def complete_workout():
    data = request.get_json()
    plan_filename, tracked_filename, csv_content = data.get('plan_filename'), data.get('tracked_filename'), data.get('csv_content')
    if current_user.role != 'coach' and not tracked_filename.startswith(current_user.username + '_'):
        return jsonify({"status": "error", "message": "Permission denied."}), 403
    with open(os.path.join(FINISHED_DIR, tracked_filename), 'w', newline='', encoding='utf-8') as f:
        f.write(csv_content)
    plan_path = os.path.join(PLANNED_DIR, plan_filename)
    if os.path.exists(plan_path):
        os.remove(plan_path)
    inprogress_path = os.path.join(INPROGRESS_DIR, tracked_filename)
    if os.path.exists(inprogress_path):
        os.remove(inprogress_path)
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
        return jsonify({"status": "success", "message": f"Plan '{filename}' deleted."})
    return jsonify({"status": "error", "message": "Plan not found."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

