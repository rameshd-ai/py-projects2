"""
Setup Script
Helps with initial project setup
"""
import os
import sys
from pathlib import Path


def check_python_version():
    """Check Python version is 3.11+"""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}")
    return True


def check_env_file():
    """Check if .env file exists"""
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if not env_file.exists():
        if env_example.exists():
            print("⚠️  .env file not found")
            print(f"   Please copy {env_example} to .env and fill in your credentials:")
            print(f"   cp {env_example} .env")
        else:
            print("❌ env.example not found")
        return False
    else:
        print("✅ .env file exists")
        return True


def check_directories():
    """Create necessary directories"""
    directories = [
        "storage/uploads",
        "storage/screenshots",
        "storage/results",
        "storage/temp",
        "logs"
    ]
    
    all_exist = True
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
            all_exist = False
        else:
            print(f"✅ Directory exists: {directory}")
    
    return True


def main():
    """Run setup checks"""
    print("=" * 60)
    print("Figma to MiBlock Component Generator - Setup Check")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Environment File", check_env_file),
        ("Directories", check_directories)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n🔍 Checking {name}...")
        result = check_func()
        results.append(result)
        print()
    
    print("=" * 60)
    if all(results):
        print("✅ All checks passed!")
        print("\nNext steps:")
        print("1. Fill in your API credentials in .env file")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Set up PostgreSQL database:")
        print("   psql -U postgres -c 'CREATE DATABASE miblock_components;'")
        print("   psql -U postgres -d miblock_components -f scripts/setup_database.sql")
        print("4. Run the server: python src/main.py")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
    print("=" * 60)


if __name__ == "__main__":
    main()



