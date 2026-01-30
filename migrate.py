"""
Database migration script for EditorWatch v2.0
Adds LLM export storage columns to analysis_results table
Run this ONCE after updating to v2.0
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
    print("Usage: python migrate_v2.py")
    sys.exit(1)

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)

print("Starting migration to v2.0 schema...")
print("This adds LLM export storage to the database")

with engine.connect() as conn:
    try:
        # Add new columns to analysis_results table
        print("\n1. Adding new columns to analysis_results...")
        
        new_columns = [
            ("session_consistency", "FLOAT"),
            ("velocity_avg", "FLOAT"),
            ("velocity_max", "FLOAT"),
            ("llm_export_json", "TEXT"),
            ("llm_export_prompt", "TEXT")
        ]
        
        for col_name, col_type in new_columns:
            try:
                print(f"   Adding {col_name}...")
                conn.execute(text(f"ALTER TABLE analysis_results ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"   ✓ Added {col_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"   ⚠️  {col_name} already exists, skipping")
                else:
                    print(f"   ❌ Error adding {col_name}: {e}")
                conn.rollback()
        
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Replace analysis/worker.py with worker_updated.py")
        print("2. Replace models.py with models_updated.py")
        print("3. Update app.py export routes with app_exports_addon_database.py")
        print("4. Restart Flask and RQ worker")
        print("5. Reanalyze submissions to generate LLM exports")
        print("\nOld submissions can be reanalyzed by triggering analysis again.")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)