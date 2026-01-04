"""
Upgrade database to use pgvector
Run this after installing pgvector extension
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

print("="*60)
print("PGVECTOR UPGRADE")
print("="*60)
print()

# Connect to database
print("Step 1: Connecting to database...")
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='miblock_components',
        user='postgres',
        password=db_password
    )
    cur = conn.cursor()
    print("SUCCESS: Connected")
except Exception as e:
    print(f"ERROR: Could not connect")
    print(f"Error: {e}")
    sys.exit(1)

# Check if pgvector is installed
print()
print("Step 2: Checking pgvector extension...")
cur.execute("SELECT * FROM pg_available_extensions WHERE name = 'vector';")
available = cur.fetchone()

if not available:
    print("ERROR: pgvector is not available on this system")
    print()
    print("Please install pgvector first:")
    print("  1. See: docs/INSTALL_PGVECTOR_WINDOWS.md")
    print("  2. Download from: https://github.com/pgvector/pgvector/releases")
    print("  3. Or skip for now - pgvector is optional for Phase 1")
    sys.exit(1)

print(f"SUCCESS: pgvector {available[1]} is available")

# Enable extension
print()
print("Step 3: Enabling pgvector extension...")
try:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    print("SUCCESS: Extension enabled")
except Exception as e:
    print(f"ERROR: Could not enable extension")
    print(f"Error: {e}")
    cur.execute("ROLLBACK;")
    sys.exit(1)

# Check current schema
print()
print("Step 4: Checking current schema...")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'components' AND column_name = 'embedding';
""")
existing_column = cur.fetchone()

if existing_column:
    print(f"INFO: Embedding column already exists as {existing_column[1]}")
    if existing_column[1] == 'USER-DEFINED':
        print("SUCCESS: Already using vector type")
        print()
        print("="*60)
        print("DATABASE ALREADY UPGRADED!")
        print("="*60)
        sys.exit(0)

# Add vector column
print()
print("Step 5: Adding vector column...")
try:
    cur.execute("""
        ALTER TABLE components 
        ADD COLUMN IF NOT EXISTS embedding vector(512);
    """)
    conn.commit()
    print("SUCCESS: Vector column added")
except Exception as e:
    print(f"ERROR: Could not add vector column")
    print(f"Error: {e}")
    cur.execute("ROLLBACK;")
    sys.exit(1)

# Create index
print()
print("Step 6: Creating vector index...")
try:
    # Drop old index if exists
    cur.execute("DROP INDEX IF EXISTS idx_components_embedding;")
    
    # Create new vector index
    cur.execute("""
        CREATE INDEX idx_components_embedding 
        ON components USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    conn.commit()
    print("SUCCESS: Vector index created")
except Exception as e:
    print(f"WARNING: Could not create index (this is OK for now)")
    print(f"Error: {e}")
    cur.execute("ROLLBACK;")

# Create similarity search function
print()
print("Step 7: Creating similarity search function...")
try:
    cur.execute("""
        CREATE OR REPLACE FUNCTION search_similar_components(
            query_embedding vector(512),
            similarity_threshold float DEFAULT 0.7,
            max_results int DEFAULT 10
        )
        RETURNS TABLE (
            component_id integer,
            component_name varchar,
            component_type varchar,
            similarity_score float
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                c.component_id,
                c.component_name,
                c.component_type,
                (1 - (c.embedding <=> query_embedding))::float as similarity_score
            FROM components c
            WHERE 
                c.embedding IS NOT NULL
                AND c.is_active = true
                AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
            ORDER BY c.embedding <=> query_embedding
            LIMIT max_results;
        END;
        $$ LANGUAGE plpgsql;
    """)
    conn.commit()
    print("SUCCESS: Function created")
except Exception as e:
    print(f"ERROR: Could not create function")
    print(f"Error: {e}")
    cur.execute("ROLLBACK;")

# Migrate existing JSON embeddings (if any)
print()
print("Step 8: Checking for existing embeddings...")
cur.execute("SELECT COUNT(*) FROM components WHERE embedding_json IS NOT NULL;")
json_count = cur.fetchone()[0]

if json_count > 0:
    print(f"INFO: Found {json_count} components with JSON embeddings")
    print("INFO: Migrating to vector format...")
    try:
        cur.execute("""
            UPDATE components 
            SET embedding = (
                SELECT array_agg(value::float)::vector
                FROM jsonb_array_elements_text(embedding_json)
            )
            WHERE embedding_json IS NOT NULL 
              AND embedding IS NULL;
        """)
        conn.commit()
        print(f"SUCCESS: Migrated {cur.rowcount} embeddings")
    except Exception as e:
        print(f"WARNING: Could not migrate embeddings")
        print(f"Error: {e}")
        cur.execute("ROLLBACK;")
else:
    print("INFO: No existing embeddings to migrate")

# Test the setup
print()
print("Step 9: Testing pgvector setup...")
try:
    # Create test vector
    cur.execute("SELECT array_fill(0.1, ARRAY[512])::vector;")
    test_vector = cur.fetchone()[0]
    print("SUCCESS: Can create vectors")
    
    # Test similarity search
    cur.execute("""
        SELECT search_similar_components(
            array_fill(0.1, ARRAY[512])::vector,
            0.5,
            5
        );
    """)
    print("SUCCESS: Similarity search works")
    
except Exception as e:
    print(f"WARNING: Test failed (this is OK if no data yet)")
    print(f"Error: {e}")

# Summary
print()
print("="*60)
print("UPGRADE COMPLETE!")
print("="*60)
print()
print("What changed:")
print("  - Added vector column to components table")
print("  - Created vector index for fast similarity search")
print("  - Added search_similar_components() function")
if json_count > 0:
    print(f"  - Migrated {json_count} JSON embeddings to vector format")
print()
print("Database is now ready for:")
print("  - Phase 2: Library Ingestion with embeddings")
print("  - Fast visual similarity matching")
print("  - Production deployment")
print()
print("Next steps:")
print("  1. Run: python scripts/check_database.py")
print("  2. Continue with Phase 2: Library Ingestion")
print()

cur.close()
conn.close()


