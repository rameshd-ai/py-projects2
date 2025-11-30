#!/bin/bash

echo "Starting CMS Workflow Manager..."
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Starting Flask application..."
python app.py


