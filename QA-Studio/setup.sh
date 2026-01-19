#!/bin/bash
# QA Studio - Linux/Mac Setup Script

echo "================================================================================"
echo "QA Studio - Quick Setup (Linux/Mac)"
echo "================================================================================"
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment"
    exit 1
fi

echo
echo "Activating virtual environment..."
source venv/bin/activate

echo
echo "Upgrading pip..."
python -m pip install --upgrade pip

echo
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

echo
echo "Installing Playwright browsers..."
playwright install

echo
echo "Creating reports directory..."
mkdir -p static/reports

echo
echo "================================================================================"
echo "Setup Complete!"
echo "================================================================================"
echo
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo
echo "To start the server:"
echo "  python app.py"
echo
