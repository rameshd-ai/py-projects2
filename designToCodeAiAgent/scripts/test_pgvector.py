"""
Test if pgvector is available and working
"""
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

try:
    import psycopg2
except ImportError:
    print("ERROR: Missing psycopg2!")
    print("Run: pip install psycopg2-binary")
    sys.exit(1)

# Load .env file
env_file = Path(__file__).parent.parent / ".env"
db_password = 'Google@1'

if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('DATABASE_PASSWORD='):
                db_password = line.split('=', 1)[1]

print("Testing pgvector installation...")
print()

# Connect
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='miblock_components',
        user='postgres',
        password=db_password
    )
    cur = conn.cursor()
except Exception as e:
    print(f"ERROR: Could not connect to database")
    print(f"Error: {e}")
    sys.exit(1)

# Test 1: Check if extension is available
print("Test 1: Check if pgvector is available on system...")
cur.execute("SELECT * FROM pg_available_extensions WHERE name = 'vector';")
available = cur.fetchone()

if available:
    print(f"  SUCCESS: pgvector {available[1]} is available")
    print(f"  Installed: {available[2]}")
else:
    print("  FAILED: pgvector is not available")
    print()
    print("Install pgvector:")
    print("  - See: docs/INSTALL_PGVECTOR_WINDOWS.md")
    print("  - Download: https://github.com/pgvector/pgvector/releases")
    print()
    print("Or skip for now - pgvector is optional for Phase 1")
    sys.exit(1)

# Test 2: Check if extension is enabled
print()
print("Test 2: Check if pgvector extension is enabled...")
cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
enabled = cur.fetchone()

if enabled:
    print(f"  SUCCESS: Extension is enabled")
else:
    print("  INFO: Extension not enabled yet")
    print("  Run: CREATE EXTENSION vector;")
    print("  Or: python scripts/upgrade_to_pgvector.py")

# Test 3: Try to create a vector
if enabled:
    print()
    print("Test 3: Test vector creation...")
    try:
        cur.execute("SELECT '[1,2,3]'::vector;")
        result = cur.fetchone()
        print(f"  SUCCESS: Can create vectors")
        print(f"  Result: {result[0]}")
    except Exception as e:
        print(f"  FAILED: {e}")

    # Test 4: Test similarity
    print()
    print("Test 4: Test cosine similarity...")
    try:
        cur.execute("""
            SELECT 
                '[1,2,3]'::vector <=> '[3,2,1]'::vector as distance,
                1 - ('[1,2,3]'::vector <=> '[3,2,1]'::vector) as similarity;
        """)
        result = cur.fetchone()
        print(f"  SUCCESS: Similarity calculation works")
        print(f"  Distance: {result[0]:.4f}")
        print(f"  Similarity: {result[1]:.4f}")
    except Exception as e:
        print(f"  FAILED: {e}")

# Summary
print()
print("="*60)
if enabled:
    print("pgvector is INSTALLED and WORKING!")
    print()
    print("Next step:")
    print("  Run: python scripts/upgrade_to_pgvector.py")
    print("  This will add vector columns to your tables")
elif available:
    print("pgvector is AVAILABLE but not enabled")
    print()
    print("Next step:")
    print("  Run: python scripts/upgrade_to_pgvector.py")
    print("  This will enable the extension and set up your tables")
else:
    print("pgvector is NOT AVAILABLE")
    print()
    print("Options:")
    print("  1. Install pgvector (see docs/INSTALL_PGVECTOR_WINDOWS.md)")
    print("  2. Skip for now and continue with Phase 1")
print("="*60)

cur.close()
conn.close()


