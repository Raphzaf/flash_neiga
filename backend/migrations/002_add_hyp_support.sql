-- Migration: Ajouter le support HYP (Version corrigée)
-- Date: 2026-01-12
-- Description: Ajoute les colonnes HYP à transactions et subscriptions

-- ===== Mise à jour de la table transactions =====

-- Ajouter les colonnes HYP si elles n'existent pas
ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS plan_id VARCHAR;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS hyp_transaction_id VARCHAR;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS hyp_internal_deal_id VARCHAR;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS payment_url VARCHAR;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS callback_data JSON;

-- Créer les index pour les colonnes HYP de transactions
CREATE INDEX IF NOT EXISTS idx_transactions_plan_id 
ON transactions(plan_id);

CREATE INDEX IF NOT EXISTS idx_transactions_hyp_transaction_id 
ON transactions(hyp_transaction_id);

CREATE INDEX IF NOT EXISTS idx_transactions_hyp_internal_deal_id 
ON transactions(hyp_internal_deal_id);

-- Ajouter contraintes UNIQUE pour colonnes HYP (ignorer si existe déjà)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'transactions_hyp_transaction_id_key'
    ) THEN
        ALTER TABLE transactions 
        ADD CONSTRAINT transactions_hyp_transaction_id_key 
        UNIQUE (hyp_transaction_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'transactions_hyp_internal_deal_id_key'
    ) THEN
        ALTER TABLE transactions 
        ADD CONSTRAINT transactions_hyp_internal_deal_id_key 
        UNIQUE (hyp_internal_deal_id);
    END IF;
END $$;

-- ===== Mise à jour/Création de la table subscriptions =====

-- Créer la table si elle n'existe pas (avec structure minimale)
CREATE TABLE IF NOT EXISTS subscriptions (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ajouter toutes les colonnes une par une (si elles n'existent pas)
ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS user_id VARCHAR;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS plan_id VARCHAR;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS license_id VARCHAR;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS product_id INTEGER;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS status VARCHAR;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS next_renewal TIMESTAMP;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP;

ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS transaction_id VARCHAR;

-- Ajouter la foreign key vers users si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'subscriptions_user_id_fkey'
    ) THEN
        ALTER TABLE subscriptions 
        ADD CONSTRAINT subscriptions_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
END $$;

-- Ajouter la foreign key vers transactions si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'subscriptions_transaction_id_fkey'
    ) THEN
        ALTER TABLE subscriptions 
        ADD CONSTRAINT subscriptions_transaction_id_fkey 
        FOREIGN KEY (transaction_id) REFERENCES transactions(id);
    END IF;
END $$;

-- Créer les index pour subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id 
ON subscriptions(user_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_plan_id 
ON subscriptions(plan_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_status 
ON subscriptions(status);

CREATE INDEX IF NOT EXISTS idx_subscriptions_license_id 
ON subscriptions(license_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_product_id 
ON subscriptions(product_id);
