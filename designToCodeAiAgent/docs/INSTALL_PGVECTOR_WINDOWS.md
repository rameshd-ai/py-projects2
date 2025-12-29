# Installing pgvector on Windows (PostgreSQL 18)

## Quick Summary

**pgvector** is optional for Phase 1. You can proceed without it and add it later in Phase 2.

If you want to install it now, here are 3 options:

---

## ✅ **Option 1: Pre-built Binary (Easiest)**

### Step 1: Download Pre-built Extension

1. Go to: https://github.com/pgvector/pgvector/releases
2. Download the Windows binary for PostgreSQL 18
3. Look for file like: `pgvector-0.7.4-windows-x64-pg18.zip`

### Step 2: Extract to PostgreSQL Directory

```powershell
# Extract to PostgreSQL extension directory
# Default location for PostgreSQL 18:
C:\Program Files\PostgreSQL\18\lib\
C:\Program Files\PostgreSQL\18\share\extension\
```

Files to copy:
- `vector.dll` → `C:\Program Files\PostgreSQL\18\lib\`
- `vector.control` → `C:\Program Files\PostgreSQL\18\share\extension\`
- `vector--*.sql` → `C:\Program Files\PostgreSQL\18\share\extension\`

### Step 3: Enable Extension

```bash
# Connect to your database
psql -U postgres -d miblock_components

# Enable extension
CREATE EXTENSION vector;

# Verify
\dx vector

# Exit
\q
```

### Step 4: Upgrade Database Schema

```bash
# Run upgrade script
psql -U postgres -d miblock_components -f docs/INSTALL_PGVECTOR.md
```

✅ **Done!** pgvector is now installed.

---

## ✅ **Option 2: Using Stack Builder (During PostgreSQL Install)**

If you haven't installed PostgreSQL yet or want to reinstall:

1. Run PostgreSQL installer again
2. Select "Stack Builder" at the end
3. In Stack Builder:
   - Select your PostgreSQL server
   - Expand "Spatial Extensions"
   - Check "pgvector"
   - Install

⚠️ **Note**: Stack Builder might not always have the latest pgvector for PostgreSQL 18. Use Option 1 if not available.

---

## ✅ **Option 3: Compile from Source (Advanced)**

### Requirements:
- Visual Studio 2022 (Community Edition)
- CMake
- PostgreSQL 18 dev files

### Steps:

1. **Clone Repository**
```bash
git clone https://github.com/pgvector/pgvector.git
cd pgvector
```

2. **Open Visual Studio Command Prompt**
```bash
# Set PostgreSQL path
set PGROOT=C:\Program Files\PostgreSQL\18

# Build
nmake /F Makefile.win

# Install
nmake /F Makefile.win install
```

3. **Enable Extension**
```bash
psql -U postgres -d miblock_components -c "CREATE EXTENSION vector;"
```

---

## 🧪 **Test pgvector Installation**

After installation, test it:

```bash
python scripts/test_pgvector.py
```

Or manually:

```sql
-- Connect to database
psql -U postgres -d miblock_components

-- Create test vector
SELECT '[1,2,3]'::vector;

-- Test similarity
SELECT 
    '[1,2,3]'::vector <=> '[3,2,1]'::vector as cosine_distance;

-- Should return a number between 0 and 2
```

---

## 🔄 **Apply Database Upgrade**

After pgvector is installed:

```bash
# Run upgrade script
psql -U postgres -d miblock_components -f docs/INSTALL_PGVECTOR.md

# Or use Python script
python scripts/upgrade_to_pgvector.py
```

This will:
- ✅ Add vector column to components table
- ✅ Create similarity search function
- ✅ Migrate existing JSON embeddings (if any)

---

## ✅ **Verify Installation**

```bash
# Check if pgvector is installed
python scripts/check_database.py
```

Should show:
```
🔌 Extensions:
   ✅ pgvector: 0.7.4
```

---

## ⚠️ **Common Issues**

### Issue 1: "could not load library"

**Solution:**
- Make sure `vector.dll` is in `PostgreSQL\18\lib\`
- Restart PostgreSQL service
- Check file permissions

### Issue 2: "extension does not exist"

**Solution:**
- Make sure `.control` and `.sql` files are in `PostgreSQL\18\share\extension\`
- Restart PostgreSQL
- Try: `SELECT * FROM pg_available_extensions WHERE name = 'vector';`

### Issue 3: "version mismatch"

**Solution:**
- Download the correct version for PostgreSQL 18
- Check: https://github.com/pgvector/pgvector/releases
- Look for "pg18" in filename

---

## 🎯 **When to Install pgvector?**

| Scenario | Recommendation |
|----------|---------------|
| **Just starting Phase 1** | ⏭️ **Skip for now** - Not needed yet |
| **Ready for Phase 2** | ✅ **Install now** - Needed for visual matching |
| **Having issues** | ⏭️ **Skip and continue** - Can add later |
| **Want full features** | ✅ **Install now** - Get complete setup |

---

## 📝 **Summary**

**Without pgvector:**
- ✅ Phase 1 works perfectly
- ✅ Can store component data
- ✅ Can generate HTML
- ⚠️ Visual similarity is slower (uses JSON)

**With pgvector:**
- ✅ Everything above
- ✅ Fast visual similarity search
- ✅ Ready for Phase 2+ immediately
- ✅ Production-ready setup

---

## 🚀 **My Recommendation**

**For now:** Proceed with Phase 1 without pgvector.

**Why?**
1. ✅ Keeps setup simple
2. ✅ You can focus on core features
3. ✅ Easy to add later (5 minutes)
4. ✅ Won't block any Phase 1 work

**When to add it:**
- When starting Phase 2 (Library Ingestion)
- When you need visual similarity
- When deploying to production

---

**Need help? See: docs/DATABASE_SETUP.md**

**Last Updated**: December 29, 2025  
**PostgreSQL Version**: 18.1  
**pgvector Version**: 0.7+

