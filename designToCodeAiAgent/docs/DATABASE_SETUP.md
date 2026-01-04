# Database Setup Guide

## 🗄️ PostgreSQL + pgvector Installation

### For Windows

#### Step 1: Install PostgreSQL

1. **Download PostgreSQL**:
   - Go to: https://www.postgresql.org/download/windows/
   - Download the installer (PostgreSQL 15 or 16)
   - Run the installer

2. **During Installation**:
   - Remember the password you set for `postgres` user
   - Default port: `5432` (keep it)
   - Install Stack Builder: **Yes** (for pgvector)

3. **Add to PATH** (if not automatic):
   ```
   C:\Program Files\PostgreSQL\15\bin
   ```

#### Step 2: Install pgvector Extension

**Option A: Using Stack Builder** (During PostgreSQL installation)
1. In Stack Builder, select "Spatial Extensions"
2. Select "pgvector"
3. Install

**Option B: Manual Installation**
1. Download pgvector from: https://github.com/pgvector/pgvector/releases
2. Extract to PostgreSQL extensions folder
3. Run: `CREATE EXTENSION vector;` in PostgreSQL

#### Step 3: Verify Installation

Open Command Prompt or PowerShell:
```bash
# Check PostgreSQL
psql --version

# Should show: psql (PostgreSQL) 15.x or 16.x
```

---

## 📊 Create Database and Tables

### Step 1: Create Database

**Option A: Using psql (Command Line)**
```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE miblock_components;

# Exit
\q
```

**Option B: Using pgAdmin** (GUI)
1. Open pgAdmin (installed with PostgreSQL)
2. Connect to PostgreSQL server
3. Right-click "Databases" → "Create" → "Database"
4. Name: `miblock_components`
5. Click "Save"

### Step 2: Run Schema Script

**Option A: Using psql (Command Line)**
```bash
# Navigate to project directory
cd D:\GItHIbProjects\py-projects2\designToCodeAiAgent

# Run the schema file
psql -U postgres -d miblock_components -f scripts/setup_database.sql

# You should see:
# CREATE EXTENSION
# CREATE TABLE
# CREATE INDEX
# ... etc
```

**Option B: Using pgAdmin (GUI)**
1. Open pgAdmin
2. Connect to `miblock_components` database
3. Click "Tools" → "Query Tool"
4. Open file: `scripts/setup_database.sql`
5. Click "Execute" (▶️ button)

---

## 👀 View Tables

### Method 1: Using psql (Command Line)

```bash
# Connect to database
psql -U postgres -d miblock_components

# List all tables
\dt

# You should see:
#  public | components             | table | postgres
#  public | generation_tasks       | table | postgres
#  public | library_refresh_tasks  | table | postgres

# View table structure
\d components
\d generation_tasks
\d library_refresh_tasks

# View indexes
\di

# Count rows (should be 0 initially)
SELECT COUNT(*) FROM components;
SELECT COUNT(*) FROM generation_tasks;
SELECT COUNT(*) FROM library_refresh_tasks;

# View component stats view
SELECT * FROM component_stats;

# Exit
\q
```

### Method 2: Using pgAdmin (GUI)

1. Open pgAdmin
2. Expand: Servers → PostgreSQL 15 → Databases → miblock_components
3. Expand "Schemas" → "public" → "Tables"
4. You'll see:
   - `components`
   - `generation_tasks`
   - `library_refresh_tasks`
5. Right-click any table → "View/Edit Data" → "All Rows"

### Method 3: Using Python Script

Create a test script:

```python
# test_database.py
import psycopg2
from tabulate import tabulate

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="miblock_components",
    user="postgres",
    password="your_password_here"
)

cur = conn.cursor()

# List all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public'
    ORDER BY table_name;
""")

tables = cur.fetchall()
print("📊 Tables in database:")
print(tabulate(tables, headers=['Table Name'], tablefmt='grid'))
print()

# Get table counts
for table in tables:
    table_name = table[0]
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"  {table_name}: {count} rows")

# View components table structure
print("\n📋 Components Table Structure:")
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'components'
    ORDER BY ordinal_position;
""")
columns = cur.fetchall()
print(tabulate(columns, headers=['Column', 'Type', 'Max Length'], tablefmt='grid'))

# Check pgvector extension
print("\n🔌 Installed Extensions:")
cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
ext = cur.fetchall()
print(tabulate(ext, headers=['OID', 'Name', 'Owner', 'Schema', 'Relocatable', 'Version'], tablefmt='grid'))

cur.close()
conn.close()
```

Run it:
```bash
pip install tabulate psycopg2-binary
python test_database.py
```

---

## 🧪 Quick Database Test

### Verify Everything Works

```sql
-- Connect to database
psql -U postgres -d miblock_components

-- Check pgvector is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Insert test component
INSERT INTO components (
    component_name,
    component_type,
    description,
    config_json,
    format_json,
    records_json,
    is_active
) VALUES (
    'Test Component',
    'TestType',
    'Test description',
    '{"test": "config"}'::jsonb,
    '{"test": "format"}'::jsonb,
    '{"test": "records"}'::jsonb,
    true
);

-- View inserted data
SELECT component_id, component_name, component_type, created_at 
FROM components;

-- Test vector column (insert test embedding)
UPDATE components 
SET embedding = array_fill(0.1, ARRAY[512])::vector 
WHERE component_id = 1;

-- Test similarity search function
SELECT * FROM search_similar_components(
    array_fill(0.1, ARRAY[512])::vector,
    0.5,
    5
);

-- Clean up test data
DELETE FROM components WHERE component_name = 'Test Component';

-- Exit
\q
```

---

## 🔧 Update .env File

After creating the database, update your `.env` file:

```bash
# Copy template
cp env.example .env

# Edit .env and update:
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=miblock_components
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password_here
DATABASE_URL=postgresql://postgres:your_password_here@localhost:5432/miblock_components
```

---

## ✅ Verify Setup is Complete

Run this checklist:

```bash
# 1. PostgreSQL installed?
psql --version
# ✅ Should show version

# 2. Database created?
psql -U postgres -l | grep miblock_components
# ✅ Should show the database

# 3. Tables created?
psql -U postgres -d miblock_components -c "\dt"
# ✅ Should show 3 tables

# 4. pgvector installed?
psql -U postgres -d miblock_components -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
# ✅ Should show vector extension

# 5. Python can connect?
python -c "import psycopg2; conn = psycopg2.connect('postgresql://postgres:PASSWORD@localhost/miblock_components'); print('✅ Connected!')"
# ✅ Should print "Connected!"
```

---

## 🚨 Troubleshooting

### "psql is not recognized"
- PostgreSQL not in PATH
- Add: `C:\Program Files\PostgreSQL\15\bin` to PATH
- Restart terminal

### "password authentication failed"
- Check password in `.env`
- Reset postgres password if needed

### "database does not exist"
- Run: `psql -U postgres -c "CREATE DATABASE miblock_components;"`

### "extension vector does not exist"
- pgvector not installed
- Install from: https://github.com/pgvector/pgvector
- Or use Stack Builder

### "permission denied"
- Run as Administrator
- Or grant permissions: `GRANT ALL ON DATABASE miblock_components TO postgres;`

---

## 📚 Useful Commands

```sql
-- List all databases
\l

-- List all tables
\dt

-- Describe table
\d table_name

-- List all indexes
\di

-- List all extensions
\dx

-- Show table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Show connection info
\conninfo

-- Execute SQL file
\i /path/to/file.sql

-- Show running queries
SELECT pid, query, state FROM pg_stat_activity WHERE datname = 'miblock_components';
```

---

## 🎯 Next Steps

After database is set up:

1. ✅ Verify all tables exist
2. ✅ Update `.env` with database credentials
3. ✅ Run Flask app: `python src/main.py`
4. ✅ Test connection from Python
5. ✅ Ready for Phase 2 (Library Ingestion)!

---

**Last Updated**: December 29, 2025  
**PostgreSQL Version**: 15+ (or 16+)  
**pgvector Version**: 0.5+



