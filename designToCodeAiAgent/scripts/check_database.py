"""
Simple Database Checker
Checks if PostgreSQL is set up correctly
"""
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

try:
    import psycopg2
    from tabulate import tabulate
except ImportError:
    print("ERROR: Missing dependencies!")
    print("Run: pip install psycopg2-binary tabulate")
    sys.exit(1)

# Load .env file directly
from pathlib import Path

env_file = Path(__file__).parent.parent / ".env"
db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'miblock_components',
    'user': 'postgres',
    'password': 'your_password'
}

if env_file.exists():
    print("✅ Loading settings from .env file")
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('DATABASE_PASSWORD='):
                db_config['password'] = line.split('=', 1)[1]
            elif line.startswith('DATABASE_HOST='):
                db_config['host'] = line.split('=', 1)[1]
            elif line.startswith('DATABASE_PORT='):
                db_config['port'] = int(line.split('=', 1)[1])
            elif line.startswith('DATABASE_NAME='):
                db_config['database'] = line.split('=', 1)[1]
            elif line.startswith('DATABASE_USER='):
                db_config['user'] = line.split('=', 1)[1]
else:
    print("⚠️  .env file not found!")
    print("Run: python scripts/create_env.py")
    sys.exit(1)

print("\n" + "="*60)
print("🗄️  DATABASE STATUS CHECK")
print("="*60 + "\n")

# Try to connect
try:
    print(f"📡 Connecting to PostgreSQL...")
    print(f"   Host: {db_config['host']}")
    print(f"   Port: {db_config['port']}")
    print(f"   Database: {db_config['database']}")
    print(f"   User: {db_config['user']}")
    print()
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    print("✅ Connected successfully!\n")
    
except psycopg2.OperationalError as e:
    print(f"❌ Connection failed!")
    print(f"   Error: {e}\n")
    print("💡 Possible solutions:")
    print("   1. Check if PostgreSQL is running")
    print("   2. Verify database exists: psql -U postgres -c 'CREATE DATABASE miblock_components;'")
    print("   3. Check credentials in .env file")
    print("   4. See: docs/DATABASE_SETUP.md")
    sys.exit(1)

# Check PostgreSQL version
print("📊 PostgreSQL Information:")
cur.execute("SELECT version();")
version = cur.fetchone()[0]
print(f"   Version: {version.split(',')[0]}")

# Check database size
cur.execute(f"SELECT pg_size_pretty(pg_database_size('{db_config['database']}'));")
size = cur.fetchone()[0]
print(f"   Database Size: {size}\n")

# Check for pgvector extension
print("🔌 Extensions:")
cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
ext = cur.fetchone()
if ext:
    print(f"   ✅ pgvector: {ext[1]}")
else:
    print("   ❌ pgvector: NOT INSTALLED")
    print("   💡 Install with: CREATE EXTENSION vector;")
print()

# List all tables
print("📋 Tables:")
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' AND table_type='BASE TABLE'
    ORDER BY table_name;
""")
tables = cur.fetchall()

if not tables:
    print("   ❌ No tables found!")
    print("   💡 Run: psql -U postgres -d miblock_components -f scripts/setup_database.sql")
    print()
else:
    for table in tables:
        table_name = table[0]
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"   ✅ {table_name}: {count} rows")
    print()

# Check indexes
print("🔍 Indexes:")
cur.execute("""
    SELECT indexname, tablename 
    FROM pg_indexes 
    WHERE schemaname = 'public' AND tablename LIKE '%component%'
    ORDER BY tablename, indexname;
""")
indexes = cur.fetchall()

if indexes:
    for idx in indexes:
        print(f"   ✅ {idx[0]} on {idx[1]}")
else:
    print("   ⚠️  No indexes found")
print()

# Check views
print("👁️  Views:")
cur.execute("""
    SELECT table_name 
    FROM information_schema.views 
    WHERE table_schema='public'
    ORDER BY table_name;
""")
views = cur.fetchall()

if views:
    for view in views:
        print(f"   ✅ {view[0]}")
else:
    print("   ⚠️  No views found")
print()

# Check functions
print("⚙️  Functions:")
cur.execute("""
    SELECT routine_name 
    FROM information_schema.routines 
    WHERE routine_schema='public' AND routine_type='FUNCTION'
    ORDER BY routine_name;
""")
functions = cur.fetchall()

if functions:
    for func in functions:
        print(f"   ✅ {func[0]}")
else:
    print("   ⚠️  No functions found")
print()

# Summary
print("="*60)
print("📊 SUMMARY")
print("="*60)

checks = []
checks.append(["Connection", "✅ Success" if conn else "❌ Failed"])
checks.append(["pgvector Extension", "✅ Installed" if ext else "❌ Not Installed"])
checks.append(["Tables", f"✅ {len(tables)} found" if tables else "❌ None found"])
checks.append(["Indexes", f"✅ {len(indexes)} found" if indexes else "⚠️  None found"])
checks.append(["Views", f"✅ {len(views)} found" if views else "⚠️  None found"])
checks.append(["Functions", f"✅ {len(functions)} found" if functions else "⚠️  None found"])

print(tabulate(checks, headers=['Check', 'Status'], tablefmt='grid'))
print()

# Next steps
if not ext or not tables:
    print("🚨 ACTION REQUIRED:")
    if not ext:
        print("   1. Install pgvector extension")
    if not tables:
        print("   2. Run database schema: psql -U postgres -d miblock_components -f scripts/setup_database.sql")
    print("   3. See: docs/DATABASE_SETUP.md for details")
else:
    print("✅ Database is ready!")
    print("   You can now:")
    print("   1. Run the Flask app: python src/main.py")
    print("   2. Start Phase 2: Library Ingestion")

print()

# Close connection
cur.close()
conn.close()


