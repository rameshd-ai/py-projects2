"""
QA Studio - Setup Script
Automates the initial setup process.
"""
import os
import sys
import subprocess
import platform
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, check=check)
    return result.returncode == 0


def main():
    """Main setup function."""
    print("=" * 80)
    print("QA Studio - Setup Script")
    print("=" * 80)
    print()
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("[ERROR] Python 3.8 or higher is required")
        print(f"   Current version: {python_version.major}.{python_version.minor}")
        sys.exit(1)
    
    print(f"[OK] Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    print()
    
    # Determine virtual environment name
    venv_name = "venv"
    venv_path = Path(venv_name)
    
    # Check if venv already exists
    if venv_path.exists():
        print(f"[WARNING] Virtual environment '{venv_name}' already exists")
        response = input("   Do you want to recreate it? (y/N): ").strip().lower()
        if response == 'y':
            print(f"   Removing existing '{venv_name}'...")
            if platform.system() == "Windows":
                run_command(f'rmdir /s /q {venv_name}', check=False)
            else:
                run_command(f'rm -rf {venv_name}', check=False)
        else:
            print("   Using existing virtual environment")
            venv_path = None
    
    # Create virtual environment
    if venv_path is None or not venv_path.exists():
        print(f"\n[INFO] Creating virtual environment '{venv_name}'...")
        if not run_command(f"{sys.executable} -m venv {venv_name}"):
            print("[ERROR] Failed to create virtual environment")
            sys.exit(1)
        print("[OK] Virtual environment created")
    
    # Determine activation script path
    if platform.system() == "Windows":
        pip_path = Path(venv_name) / "Scripts" / "pip.exe"
        python_path = Path(venv_name) / "Scripts" / "python.exe"
    else:
        pip_path = Path(venv_name) / "bin" / "pip"
        python_path = Path(venv_name) / "bin" / "python"
    
    # Upgrade pip
    print("\n[INFO] Upgrading pip...")
    if not run_command(f'"{pip_path}" install --upgrade pip'):
        print("[WARNING] Failed to upgrade pip, continuing anyway...")
    
    # Install requirements
    print("\n[INFO] Installing dependencies from requirements.txt...")
    if not Path("requirements.txt").exists():
        print("[ERROR] requirements.txt not found")
        sys.exit(1)
    
    if not run_command(f'"{pip_path}" install -r requirements.txt'):
        print("[ERROR] Failed to install dependencies")
        sys.exit(1)
    print("[OK] Dependencies installed")
    
    # Install Playwright browsers
    print("\n[INFO] Installing Playwright browsers...")
    playwright_path = Path(venv_name) / "Scripts" / "playwright.exe" if platform.system() == "Windows" else Path(venv_name) / "bin" / "playwright"
    if not run_command(f'"{playwright_path}" install'):
        print("[WARNING] Failed to install Playwright browsers")
        print("   You can install them manually later with: playwright install")
    
    # Create reports directory
    print("\n[INFO] Creating reports directory...")
    reports_dir = Path("static") / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    print("[OK] Reports directory created")
    
    # Summary
    print("\n" + "=" * 80)
    print("[OK] Setup Complete!")
    print("=" * 80)
    print()
    print("Next steps:")
    print()
    
    if platform.system() == "Windows":
        print("1. Activate virtual environment:")
        print("   .\\venv\\Scripts\\Activate.ps1")
        print("   (or: venv\\Scripts\\activate.bat for CMD)")
    else:
        print("1. Activate virtual environment:")
        print("   source venv/bin/activate")
    
    print()
    print("2. Start the server:")
    print("   python app.py")
    print()
    print("3. Open your browser to:")
    print("   http://localhost:5000")
    print()
    print("=" * 80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[ERROR] Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Error: {e}")
        sys.exit(1)
