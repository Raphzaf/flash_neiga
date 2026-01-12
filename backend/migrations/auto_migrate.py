"""
Automatic migration that runs on startup
Adds all HYP-required columns to transactions and subscriptions tables
"""
import logging
from sqlalchemy import text, inspect

# Support imports both when running from backend/ and from repo root
try:
    from database import engine
except ImportError:
    from backend.database import engine

logger = logging.getLogger(__name__)


def run_hyp_migration():
    """
    Add HYP columns to transactions and subscriptions tables
    Safe to run multiple times (idempotent)
    """
    try:
        logger.info("🔧 Starting HYP database migration...")
        
        inspector = inspect(engine)
        
        # Determine if we're using PostgreSQL or SQLite
        is_postgresql = 'postgresql' in str(engine.url)
        
        # === TRANSACTIONS TABLE ===
        if 'transactions' in inspector.get_table_names():
            logger.info("📊 Checking transactions table...")
            existing_cols = {col['name'] for col in inspector.get_columns('transactions')}
            
            required_cols = {
                'plan_id': 'VARCHAR',
                'hyp_transaction_id': 'VARCHAR',
                'hyp_internal_deal_id': 'VARCHAR',
                'payment_url': 'TEXT',
                'callback_data': 'JSON' if is_postgresql else 'TEXT',
                'event_data': 'JSON' if is_postgresql else 'TEXT'
            }
            
            with engine.connect() as conn:
                for col_name, col_type in required_cols.items():
                    if col_name not in existing_cols:
                        logger.info(f"   ➕ Adding transactions.{col_name} ({col_type})")
                        if is_postgresql:
                            # PostgreSQL supports IF NOT EXISTS
                            conn.execute(text(f"ALTER TABLE transactions ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        else:
                            # SQLite doesn't support IF NOT EXISTS, but we already checked
                            conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    else:
                        logger.debug(f"   ✅ transactions.{col_name} exists")
                
                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_plan_id ON transactions(plan_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_hyp_transaction_id ON transactions(hyp_transaction_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_hyp_internal_deal_id ON transactions(hyp_internal_deal_id)"))
                conn.commit()
                logger.info("   ✅ Transactions indexes created")
        
        # === SUBSCRIPTIONS TABLE ===
        if 'subscriptions' in inspector.get_table_names():
            logger.info("📊 Checking subscriptions table...")
            existing_cols = {col['name'] for col in inspector.get_columns('subscriptions')}
            
            if is_postgresql:
                required_cols = {
                    'plan_id': 'VARCHAR',
                    'license_id': 'VARCHAR',
                    'product_id': 'INTEGER',
                    'start_date': 'TIMESTAMP',
                    'end_date': 'TIMESTAMP',
                    'status': 'VARCHAR',
                    'next_renewal': 'TIMESTAMP',
                    'canceled_at': 'TIMESTAMP',
                    'transaction_id': 'VARCHAR',
                    'created_at': 'TIMESTAMP DEFAULT NOW()',
                    'updated_at': 'TIMESTAMP DEFAULT NOW()'
                }
            else:
                # SQLite uses different syntax for defaults
                required_cols = {
                    'plan_id': 'VARCHAR',
                    'license_id': 'VARCHAR',
                    'product_id': 'INTEGER',
                    'start_date': 'TIMESTAMP',
                    'end_date': 'TIMESTAMP',
                    'status': 'VARCHAR',
                    'next_renewal': 'TIMESTAMP',
                    'canceled_at': 'TIMESTAMP',
                    'transaction_id': 'VARCHAR',
                    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                    'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                }
            
            with engine.connect() as conn:
                for col_name, col_type in required_cols.items():
                    if col_name not in existing_cols:
                        logger.info(f"   ➕ Adding subscriptions.{col_name} ({col_type})")
                        if is_postgresql:
                            conn.execute(text(f"ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        else:
                            conn.execute(text(f"ALTER TABLE subscriptions ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                    else:
                        logger.debug(f"   ✅ subscriptions.{col_name} exists")
                
                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_plan_id ON subscriptions(plan_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_transaction_id ON subscriptions(transaction_id)"))
                conn.commit()
                logger.info("   ✅ Subscriptions indexes created")
        
        logger.info("✅ HYP migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ HYP migration failed: {e}")
        # Don't raise - let the app start even if migration fails
        return False
