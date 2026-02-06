@echo off
echo ========================================
echo Zerodha Token Generator
echo ========================================
echo.
echo This will:
echo 1. Open Zerodha login in your browser
echo 2. Generate access token automatically  
echo 3. Save it to config.json
echo.
echo Press any key to continue...
pause > nul

python generate_token.py

echo.
echo ========================================
echo.
pause
