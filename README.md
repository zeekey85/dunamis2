Dunamis Workout Planner & Tracker
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
