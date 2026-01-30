"""
Database migration script for EditorWatch
Run this ONCE before deploying the new code
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from .env if present
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)

print("Starting migration...")

with engine.connect() as conn:
    try:
        # Check if required_fields column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='assignments' AND column_name='required_fields'
        """))
        
        if result.rowcount == 0:
            print("Adding required_fields column to assignments...")
            conn.execute(text("""
                ALTER TABLE assignments 
                ADD COLUMN required_fields TEXT DEFAULT '["matricule"]'
            """))
            conn.commit()
            print("✅ Added required_fields column")
        else:
            print("⚠️  required_fields already exists, skipping")
        
        # Check if student_info column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='submissions' AND column_name='student_info'
        """))
        
        if result.rowcount == 0:
            print("Migrating student_id to student_info...")
            
            # Add new column
            conn.execute(text("""
                ALTER TABLE submissions 
                ADD COLUMN student_info TEXT
            """))
            
            # Migrate data: {"matricule": "old_student_id"}
            conn.execute(text("""
                UPDATE submissions 
                SET student_info = json_build_object('matricule', student_id)::text
                WHERE student_info IS NULL
            """))
            
            # Drop old column (optional - comment out if you want to keep it)
            # conn.execute(text("ALTER TABLE submissions DROP COLUMN student_id"))
            
            conn.commit()
            print("✅ Migrated student_id to student_info")
        else:
            print("⚠️  student_info already exists, skipping")
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)