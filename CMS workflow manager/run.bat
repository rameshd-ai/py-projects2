@echo off
echo Starting CMS Workflow Manager...
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting Flask application...
python app.py

pause









