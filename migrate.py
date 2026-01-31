"""
Database migration script for EditorWatch v2.0
Adds LLM export storage columns to analysis_results table
Run this ONCE after updating to v2.0
"""
import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# lightweight logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('editorwatch.migrate')

# Load environment variables from .env if present
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    logger.error('ERROR: DATABASE_URL not set')
    logger.info('Usage: python migrate_v2.py')
    sys.exit(1)

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)

logger.info('Starting migration to v2.0 schema...')
logger.info('This adds LLM export storage to the database')

with engine.connect() as conn:
    try:
        # Add new columns to analysis_results table
        logger.info('Adding new columns to analysis_results...')
        
        new_columns = [
            ("session_consistency", "FLOAT"),
            ("velocity_avg", "FLOAT"),
            ("velocity_max", "FLOAT"),
            ("llm_export_json", "TEXT"),
            ("llm_export_prompt", "TEXT")
        ]
        
        for col_name, col_type in new_columns:
            try:
                logger.info('Adding %s...', col_name)
                conn.execute(text(f"ALTER TABLE analysis_results ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                logger.info('Added %s', col_name)
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.warning('%s already exists, skipping', col_name)
                else:
                    logger.error('Error adding %s: %s', col_name, e)
                conn.rollback()
        
        logger.info('Migration completed successfully')
        logger.info('Next steps: replace worker/models and restart services as needed; reanalyze submissions to generate exports')
        
    except Exception as e:
        logger.exception('Migration failed: %s', e)
        conn.rollback()
        sys.exit(1)