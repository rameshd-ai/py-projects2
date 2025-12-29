"""
Create .env file with database credentials
"""
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Get project root
project_root = Path(__file__).parent.parent

# Read template
env_example = project_root / "env.example"
env_file = project_root / ".env"

print("Creating .env file...")
print()

# Check if .env already exists
if env_file.exists():
    response = input("WARNING: .env file already exists. Overwrite? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled.")
        exit(0)

# Database password
db_password = "Google@1"
print(f"Database Password: {db_password}")
print()

# Read template
with open(env_example, 'r') as f:
    content = f.read()

# Replace database password
content = content.replace('DATABASE_PASSWORD=your_postgres_password', f'DATABASE_PASSWORD={db_password}')
content = content.replace(
    'DATABASE_URL=postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT}/${DATABASE_NAME}',
    f'DATABASE_URL=postgresql://postgres:{db_password}@localhost:5432/miblock_components'
)

# Update comment about FastAPI to Flask
content = content.replace('# FastAPI Server', '# Flask Server')

# Write .env file
with open(env_file, 'w') as f:
    f.write(content)

print(f"SUCCESS: Created {env_file}")
print()
print("Next steps:")
print("   1. Edit .env and add your API keys:")
print("      - FIGMA_API_TOKEN")
print("      - ANTHROPIC_API_KEY")
print("      - CMS_API_KEY")
print("   2. Test database connection: python scripts/check_database.py")
print()

