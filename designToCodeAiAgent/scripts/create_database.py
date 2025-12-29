"""
Create database and run schema
Usage: python scripts/create_database.py [--force]
       --force: Drop existing database without asking
"""
import sys
from pathlib import Path

# Check for --force flag
force_recreate = '--force' in sys.argv

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
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

print("="*60)
print("DATABASE SETUP")
print("="*60)
print()

# Step 1: Connect to postgres database
print("Step 1: Connecting to PostgreSQL...")
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='postgres',  # Connect to default postgres database
        user='postgres',
        password=db_password
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    print("SUCCESS: Connected to PostgreSQL")
except Exception as e:
    print(f"ERROR: Could not connect to PostgreSQL")
    print(f"Error: {e}")
    print()
    print("Possible solutions:")
    print("  1. Check if PostgreSQL is running")
    print("  2. Verify password in .env is correct")
    print("  3. Check PostgreSQL service is started")
    sys.exit(1)

# Step 2: Check if database exists
print()
print("Step 2: Checking if database exists...")
cur.execute("SELECT 1 FROM pg_database WHERE datname='miblock_components'")
exists = cur.fetchone()

if exists:
    print("INFO: Database 'miblock_components' already exists")
    if force_recreate:
        print("Dropping database (--force flag)...")
        cur.execute("DROP DATABASE miblock_components")
        exists = None
    else:
        try:
            response = input("Drop and recreate? (y/N): ")
            if response.lower() == 'y':
                print("Dropping database...")
                cur.execute("DROP DATABASE miblock_components")
                exists = None
        except (EOFError, KeyboardInterrupt):
            print()
            print("Skipping... Will try to update existing database")
            print("Use --force flag to automatically recreate")

if not exists:
    print("Creating database 'miblock_components'...")
    cur.execute("CREATE DATABASE miblock_components")
    print("SUCCESS: Database created")

cur.close()
conn.close()

# Step 3: Connect to new database and create schema
print()
print("Step 3: Creating tables and schema...")
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='miblock_components',
        user='postgres',
        password=db_password
    )
    cur = conn.cursor()
    
    # Read schema file (use simple version without pgvector for now)
    schema_file = Path(__file__).parent / "setup_database_simple.sql"
    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {schema_file}")
        sys.exit(1)
    
    print(f"Using: {schema_file.name}")
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Execute schema
    print("Running schema file...")
    cur.execute(schema_sql)
    conn.commit()
    
    print("SUCCESS: Schema created")
    
    # Verify tables
    print()
    print("Step 4: Verifying tables...")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public' AND table_type='BASE TABLE'
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    
    if tables:
        print(f"SUCCESS: {len(tables)} tables created:")
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("WARNING: No tables found")
    
    # Check pgvector (optional for Phase 1)
    print()
    print("Step 5: Checking pgvector extension (optional for Phase 1)...")
    cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
    ext = cur.fetchone()
    
    if ext:
        print("SUCCESS: pgvector extension installed")
    else:
        print("INFO: pgvector not installed (will be added in Phase 2)")
        print("      For now, embeddings stored as JSON")
    
    cur.close()
    conn.close()
    
    print()
    print("="*60)
    print("DATABASE SETUP COMPLETE!")
    print("="*60)
    print()
    print("Next steps:")
    print("  1. Run: python scripts/check_database.py")
    print("  2. Start Flask app: python src/main.py")
    print()
    
except Exception as e:
    print(f"ERROR: Failed to create schema")
    print(f"Error: {e}")
    sys.exit(1)

