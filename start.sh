#!/bin/bash

# Change to the project directory
cd /home/zak/dunamis_dev

# Activate the virtual environment
source /home/zak/venv/bin/activate

# Start Gunicorn and log all output to a file in the same directory
/home/zak/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 server:app >> workoutapp.log 2>&1
