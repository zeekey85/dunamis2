Dunamis Workout Tracker - Update 17Sep2025
Dunamis is a lightweight, self-hosted web application designed for personal trainers and coaches to plan, track, and analyze athlete workouts. It is built with a Python Flask backend and a vanilla JavaScript frontend, operating on a simple, file-based data storage system. This makes it easy to deploy on low-power hardware like a Raspberry Pi.

Key Features
Workout Planner: Design detailed daily workouts, including sets, reps, weight ramps, and supersets.

Workout Tracker: A simple interface for athletes or coaches to record performance during a session, including reps, weight, RIR, and personal notes.

Performance Analysis: Visualize historical performance for any exercise, tracking max weight and total volume over time.

Athlete Management: A web-based interface to add, edit, and remove athletes from the official roster.

Email Notifications: Automatically emails a completed workout summary to the athlete upon completion.

File-Based: No complex database setup required. All data is stored in human-readable .csv files.

How It Works
The application operates on a simple data flow centered around .csv files:

Planning: When a coach saves a new workout on the Planner page, a detailed, set-by-set .csv file is generated and saved in the planned_workouts folder. This file includes the full structure of the workout, with blank columns for future tracking (e.g., Actual Reps, RIR).

Tracking: When a workout is started from the Tracker page, the application reads the corresponding file. If it's a new workout, it reads from planned_workouts. If it's being resumed, it reads from inprogress_workouts.

Saving Progress: Clicking "Save Progress" saves the current state of the tracker to a new _tracked.csv file in the inprogress_workouts folder.

Completion: Clicking "Complete Workout" saves the final version to the finished_workouts folder, removes the original plan from planned_workouts, and deletes any in-progress versions. It then triggers the Python email function to send the results.

File Structure
The project is organized into several key directories:

dunamis/
├── api/
│   ├── emails.csv         # Stores athlete names and email addresses.
│   └── exercises.csv      # A list of all available exercises.
├── assets/
│   └── logo.png           # Application logo.
├── finished_workouts/     # Stores completed workout .csv files.
├── inprogress_workouts/   # Temporarily stores workouts being tracked.
├── planned_workouts/      # Stores upcoming workout .csv files.
├── web/
│   ├── index.html         # The Planner page.
│   ├── Workout.html       # The Tracker page.
│   └── ... (other HTML files)
├── .env                 # Stores email credentials securely (must be created manually).
├── .gitignore           # Specifies files and folders for Git to ignore.
├── dunamis_app.log        # The application log file.
├── requirements.txt       # A list of required Python packages.
├── server.py              # The main Flask web server.
└── start.sh               # The startup script for the Gunicorn server.

Raspberry Pi 5 Deployment: A Complete Guide
These instructions detail how to deploy the application on a fresh Raspberry Pi 5 running Raspberry Pi OS, using Gunicorn as the application server and Nginx as a reverse proxy.

Step 1: System Preparation and Prerequisites
Install all necessary system packages.

sudo apt update && sudo apt upgrade -y
sudo apt install git python3-pip python3-venv nginx samba samba-common-bin -y

Step 2: Get the Application Code
Clone your repository from GitHub into the pi user's home directory.

cd /home/pi
git clone <your-repository-url> dunamis
cd dunamis

Step 3: Setup Python Environment
Create a virtual environment and install the required packages.

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

Step 4: Configure Email Notifications
The application sends email using your Gmail account. For security, this requires a special App Password.

Enable 2-Step Verification: You cannot create an App Password unless 2-Step Verification is turned on for your Google account.

Generate an App Password:

Go to your Google Account's App Passwords page.

Under "Select app," choose Mail.

Under "Select device," choose Other (Custom name) and call it "Dunamis App".

Google will provide a 16-character password. Copy this password.

Create the .env File:
This file will securely store your credentials. Create it in your project directory:

nano /home/pi/dunamis/.env

Add Your Credentials:
Paste the following content into the file, replacing the placeholders with your Gmail address and the 16-character App Password.

EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your16characterapppassword
EMAIL_SERVER=smtp.gmail.com
EMAIL_PORT=587

Save and exit (Ctrl+X, then Y, then Enter).

Step 5: Configure the Startup Script
Your start.sh script needs to be made executable and updated to load your email credentials.

Open the script:

nano start.sh

Ensure its content is:

#!/bin/bash
cd /home/pi/dunamis
source venv/bin/activate
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
venv/bin/gunicorn --workers 3 --bind unix:dunamis.sock -m 007 server:app

Make it executable:

chmod +x start.sh

Step 6: Create and Enable the systemd Service
This will make your application run automatically on boot.

Create the service file:

sudo nano /etc/systemd/system/dunamis.service

Add the following content:

[Unit]
Description=Gunicorn instance to serve the Dunamis workout tracker
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/dunamis
ExecStart=/home/pi/dunamis/start.sh
Restart=always

[Install]
WantedBy=multi-user.target

Reload, Start, and Enable the Service:

sudo systemctl daemon-reload
sudo systemctl start dunamis
sudo systemctl enable dunamis

Step 7: Configure .gitignore
Before you commit any changes, it's crucial to tell Git which files to ignore.

Create the .gitignore file:

nano .gitignore

Add the following content:

# Python
__pycache__/
*.pyc
venv/

# Environment variables
.env

# Log files
*.log

# Workout Data Files
planned_workouts/*.csv
inprogress_workouts/*.csv
finished_workouts/*.csv

Step 8: Finalize Data Files
Ensure the api directory contains the necessary starting files.

api/exercises.csv: Should have a header Exercise and a list of exercises.

api/emails.csv: Should have headers Athlete,Email. You can manage this file via the "Manage Athletes" page.

Managing the Application
User and Athlete Management
Login: The application has one hardcoded user: coach with password get$trong@dunamis.

Athlete Roster: The official list of athletes is managed in the api/emails.csv file. The Manage Athletes page provides a web interface to add, edit, and delete entries in this file.

Checking Logs
The application and server logs are written to dunamis_app.log in your project's root directory. The best way to monitor the app in real-time is with the tail command:

tail -f /home/pi/dunamis/dunamis_app.log







Old update: Dunamis Workout Planner & Tracker
Dunamis is a lightweight, file-based web application for coaches to plan, assign, and track workouts for their athletes. Built with a Python Flask backend and a vanilla JavaScript frontend, it is designed to be simple, extensible, and easy to deploy on low-power hardware like a Raspberry Pi.

Key Features
Coach-Centric Design: A single coach login provides access to manage all athlete data.
Workout Planner:
Create detailed, day-by-day workout plans.
Program individual exercises, supersets, and weight ramps.
Add custom exercises to a persistent list.
Import from past workouts to use them as templates.
Workout Tracker:
Athletes can load planned workouts or resume in-progress sessions.
Track actual reps, weight, and RIR (Reps in Reserve) for each set.
View an exercise's most recent performance history while tracking.
Add session-specific notes for each exercise.
Performance Analysis:
Visualize athlete progression with charts for max weight and total volume.
Review a complete logbook of every finished workout.
File-Based Storage: All workout data is stored in human-readable .csv files, making it portable and easy to back up.
File Structure
The project uses a simple folder structure to organize workout data and application files.

/
├── server.py               # Main Flask application logic and API endpoints
├── wsgi.py                 # WSGI entry point for Gunicorn
|
├── api/
│   ├── exercises.csv       # Master list of available exercises
│   └── users.db            # SQLite database for session management
│
├── assets/
│   └── logo.png            # Application logo
│
├── finished_workouts/      # Stores completed workout CSV files with tracked data
│
├── inprogress_workouts/    # Temporarily stores workouts being actively tracked
│
├── planned_workouts/       # Stores new workout plans before they are started
│
└── web/
    ├── index.html          # The Workout Planner page
    ├── Workout.html        # The Workout Tracker page
    ├── analysis.html       # The Performance Analysis page
    └── Users.html          # The Athlete Management page

Local Development Setup
Follow these steps to run the application on your local machine for development.

1. Prerequisites
Python 3.8 or newer
pip and venv (usually included with Python)
2. Create a Virtual Environment
It is highly recommended to use a virtual environment to manage project dependencies.

# Navigate to your project directory
cd /path/to/your/project

# Create the virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS and Linux:
source venv/bin/activate
# On Windows:
.\\venv\\Scripts\\activate

3. Install Required Packages
The required Python packages are listed in requirements.txt.

Flask==3.0.3
Flask-Cors==4.0.1
Flask-Login==0.6.3
gunicorn==22.0.0
pandas==2.2.2
Werkzeug==3.0.3

Install them all with a single command:

pip install -r requirements.txt

4. Run the Development Server
Once the packages are installed, you can start the Flask development server:

python server.py

The application will be running at http://127.0.0.1:5000.

Deployment on a Raspberry Pi 5
To run this application as a persistent service on a Raspberry Pi, we will use Gunicorn as the web server and systemd to manage the process.

1. Install Gunicorn
Ensure your virtual environment is activated and install Gunicorn.

pip install gunicorn

2. Create a WSGI Entry Point
Create a file named wsgi.py in the root of your project directory. This file allows Gunicorn to find and run your Flask application.

wsgi.py

from server import app as application

if __name__ == "__main__":
    application.run()

3. Create a systemd Service File
systemd is the standard service manager on most Linux distributions, including Raspberry Pi OS. We will create a service file to tell it how to run our application.

Create a new file called dunamis.service:

sudo nano /etc/systemd/system/dunamis.service

Paste the following content into the file. You must replace /home/pi/dunamis with the actual full path to your project directory.

/etc/systemd/system/dunamis.service

[Unit]
Description=Gunicorn instance to serve the Dunamis workout tracker
After=network.target

[Service]
# User that will run the service
User=pi

# The directory where your project is located
WorkingDirectory=/home/pi/dunamis

# The command to start the Gunicorn server
# This points to the gunicorn executable inside your virtual environment
ExecStart=/home/pi/dunamis/venv/bin/gunicorn --workers 3 --bind unix:dunamis.sock -m 007 wsgi:application

# Restart the service if it fails
Restart=always

[Install]
WantedBy=multi-user.target

Save the file and exit the editor (Ctrl+X, then Y, then Enter).

4. Start and Enable the Service
Now, you can manage the service using systemctl commands.

# Reload systemd to recognize the new service file
sudo systemctl daemon-reload

# Start the Dunamis service immediately
sudo systemctl start dunamis

# Enable the service to start automatically on boot
sudo systemctl enable dunamis

# Check the status of the service to ensure it's running correctly
sudo systemctl status dunamis

5. (Recommended) Configure Nginx as a Reverse Proxy
While Gunicorn is running the application, it's best practice to use a web server like Nginx to handle incoming traffic and forward it to Gunicorn. This improves security and performance.

You would typically configure Nginx to listen on port 80 and proxy requests to the dunamis.sock file created by Gunicorn. This step is optional but highly recommended for a production environment.





Initial commit for Dunamis workout app! 100% vibe coded. 
