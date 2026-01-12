"""
Admin endpoint to run database migrations manually
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text, inspect
import os
import logging

# Support imports both when running from backend/ and from repo root
try:
    from database import engine
except ImportError:
    from backend.database import engine

try:
    from models import User
except ImportError:
    from backend.models import User

try:
    from auth import get_current_user
except ImportError:
    from backend.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/run-migration")
async def run_migration(current_user: User = Depends(get_current_user)):
    """
    Run HYP database migration manually
    Adds missing columns to transactions and subscriptions tables
    """
    try:
        migration_log = []
        
        # Check current schema
        inspector = inspect(engine)
        
        # Check transactions table
        migration_log.append("🔍 Checking transactions table...")
        if 'transactions' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('transactions')}
            migration_log.append(f"   Existing columns: {', '.join(sorted(existing_cols))}")
            
            required_cols = {
                'plan_id': 'VARCHAR',
                'hyp_transaction_id': 'VARCHAR',
                'hyp_internal_deal_id': 'VARCHAR',
                'payment_url': 'TEXT',
                'callback_data': 'JSON',
                'event_data': 'JSON'
            }
            
            with engine.connect() as conn:
                for col_name, col_type in required_cols.items():
                    if col_name not in existing_cols:
                        migration_log.append(f"   ➕ Adding column: {col_name} ({col_type})")
                        conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    else:
                        migration_log.append(f"   ✅ Column exists: {col_name}")
                
                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_plan_id ON transactions(plan_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_hyp_transaction_id ON transactions(hyp_transaction_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_hyp_internal_deal_id ON transactions(hyp_internal_deal_id)"))
                conn.commit()
                migration_log.append("   ✅ Indexes created")
        else:
            migration_log.append("   ⚠️  transactions table does not exist")
        
        # Check subscriptions table
        migration_log.append("\n🔍 Checking subscriptions table...")
        if 'subscriptions' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('subscriptions')}
            migration_log.append(f"   Existing columns: {', '.join(sorted(existing_cols))}")
            
            required_cols = {
                'plan_id': 'VARCHAR',
                'license_id': 'VARCHAR',
                'product_id': 'INTEGER',
                'start_date': 'TIMESTAMP',
                'end_date': 'TIMESTAMP',
                'status': 'VARCHAR',
                'next_renewal': 'TIMESTAMP',
                'canceled_at': 'TIMESTAMP',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            with engine.connect() as conn:
                for col_name, col_type in required_cols.items():
                    if col_name not in existing_cols:
                        migration_log.append(f"   ➕ Adding column: {col_name} ({col_type})")
                        conn.execute(text(f"ALTER TABLE subscriptions ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    else:
                        migration_log.append(f"   ✅ Column exists: {col_name}")
                
                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_plan_id ON subscriptions(plan_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)"))
                conn.commit()
                migration_log.append("   ✅ Indexes created")
        else:
            migration_log.append("   ⚠️  subscriptions table does not exist")
        
        migration_log.append("\n✅ Migration completed successfully!")
        
        return {
            "success": True,
            "message": "Database migration completed",
            "log": "\n".join(migration_log)
        }
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )
