"""
Database migration script for EditorWatch v2
Run this ONCE to migrate from old schema to new schema
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

print("Starting migration to v2 schema...")

with engine.connect() as conn:
    try:
        # 1. Create new student_codes table
        print("Creating student_codes table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS student_codes (
                id SERIAL PRIMARY KEY,
                assignment_id VARCHAR(50) NOT NULL,
                email VARCHAR(200) NOT NULL,
                code VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id),
                UNIQUE (assignment_id, email)
            )
        """))
        conn.commit()
        print("✅ student_codes table created")
        
        # 2. Drop old columns from assignments table
        print("Cleaning up assignments table...")
        try:
            conn.execute(text("ALTER TABLE assignments DROP COLUMN IF EXISTS required_fields"))
            conn.commit()
            print("✅ Removed required_fields from assignments")
        except Exception as e:
            print(f"⚠️  Could not drop required_fields: {e}")
        
        # 3. Update submissions table
        print("Updating submissions table...")
        
        # Add email column if it doesn't exist
        try:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN email VARCHAR(200)"))
            conn.commit()
            print("✅ Added email column to submissions")
        except Exception as e:
            print(f"⚠️  email column may already exist: {e}")
        
        # Drop code_encrypted column
        try:
            conn.execute(text("ALTER TABLE submissions DROP COLUMN IF EXISTS code_encrypted"))
            conn.commit()
            print("✅ Removed code_encrypted from submissions")
        except Exception as e:
            print(f"⚠️  Could not drop code_encrypted: {e}")
        
        # Drop student_info column
        try:
            conn.execute(text("ALTER TABLE submissions DROP COLUMN IF EXISTS student_info"))
            conn.commit()
            print("✅ Removed student_info from submissions")
        except Exception as e:
            print(f"⚠️  Could not drop student_info: {e}")
        
        # 4. Update analysis_results table
        print("Updating analysis_results table...")
        try:
            conn.execute(text("ALTER TABLE analysis_results ADD COLUMN flags TEXT"))
            conn.commit()
            print("✅ Added flags column to analysis_results")
        except Exception as e:
            print(f"⚠️  flags column may already exist: {e}")
        
        # 5. Add unique constraint to submissions (assignment_id, email)
        print("Adding unique constraint to submissions...")
        try:
            conn.execute(text("""
                ALTER TABLE submissions 
                ADD CONSTRAINT _assignment_student_uc 
                UNIQUE (assignment_id, email)
            """))
            conn.commit()
            print("✅ Added unique constraint")
        except Exception as e:
            print(f"⚠️  Constraint may already exist: {e}")
        
        print("\n✅ Migration completed successfully!")
        print("\n⚠️  IMPORTANT: Old submissions with student_info will need manual migration")
        print("   Run this SQL to migrate existing submissions:")
        print("""
        -- Example: Extract email from JSON student_info
        UPDATE submissions 
        SET email = student_info::json->>'email'
        WHERE email IS NULL AND student_info IS NOT NULL;
        """)
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)