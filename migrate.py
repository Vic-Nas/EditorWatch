"""
Database migration script for EditorWatch - FIX student_id issue
Run this to remove student_id column and use student_info instead
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
    print("Set it with: export DATABASE_URL='your-database-url'")
    sys.exit(1)

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)

print("Starting migration to remove student_id...")
print(f"Database: {DATABASE_URL[:50]}...")

with engine.connect() as conn:
    try:
        # Check if student_id column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='submissions' AND column_name='student_id'
        """))
        
        has_student_id = result.fetchone() is not None
        
        if has_student_id:
            print("\n1. Found student_id column - migrating data...")
            
            # Check if student_info exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='submissions' AND column_name='student_info'
            """))
            
            has_student_info = result.fetchone() is not None
            
            if not has_student_info:
                print("2. Adding student_info column...")
                conn.execute(text("""
                    ALTER TABLE submissions 
                    ADD COLUMN student_info TEXT
                """))
                conn.commit()
                print("   ✅ Added student_info column")
            
            # Migrate existing data from student_id to student_info
            print("3. Migrating data from student_id to student_info...")
            conn.execute(text("""
                UPDATE submissions 
                SET student_info = json_build_object('matricule', student_id::text)::text
                WHERE student_info IS NULL OR student_info = ''
            """))
            conn.commit()
            print("   ✅ Data migrated")
            
            # Drop the student_id column
            print("4. Dropping student_id column...")
            conn.execute(text("""
                ALTER TABLE submissions 
                DROP COLUMN student_id
            """))
            conn.commit()
            print("   ✅ Dropped student_id column")
            
        else:
            print("⚠️  student_id column doesn't exist - already migrated?")
            
            # Make sure student_info exists and is NOT NULL
            result = conn.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns 
                WHERE table_name='submissions' AND column_name='student_info'
            """))
            
            col_info = result.fetchone()
            if col_info:
                print(f"   student_info exists, nullable: {col_info[1]}")
                if col_info[1] == 'YES':
                    print("   Making student_info NOT NULL...")
                    conn.execute(text("""
                        UPDATE submissions 
                        SET student_info = '{}'::text
                        WHERE student_info IS NULL
                    """))
                    conn.execute(text("""
                        ALTER TABLE submissions 
                        ALTER COLUMN student_info SET NOT NULL
                    """))
                    conn.commit()
                    print("   ✅ student_info is now NOT NULL")
            else:
                print("   ERROR: student_info column doesn't exist!")
                sys.exit(1)
        
        # Check required_fields column in assignments
        print("\n5. Checking assignments table...")
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='assignments' AND column_name='required_fields'
        """))
        
        if result.fetchone() is None:
            print("   Adding required_fields column to assignments...")
            conn.execute(text("""
                ALTER TABLE assignments 
                ADD COLUMN required_fields TEXT DEFAULT '["matricule"]'
            """))
            conn.commit()
            print("   ✅ Added required_fields column")
        else:
            print("   ✅ required_fields already exists")
        
        print("\n" + "="*50)
        print("✅ Migration completed successfully!")
        print("="*50)
        print("\nYour database schema now matches the code:")
        print("  - submissions.student_info (JSON text)")
        print("  - NO student_id column")
        print("  - assignments.required_fields")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)