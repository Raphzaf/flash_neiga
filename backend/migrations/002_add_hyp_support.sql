-- Migration: Ajouter le support HYP
-- Date: 2026-01-12
-- Description: Ajoute les colonnes HYP à transactions et crée la table subscriptions

-- ===== Mise à jour de la table transactions =====

-- Ajouter les colonnes HYP si elles n'existent pas
ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS plan_id VARCHAR;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS hyp_transaction_id VARCHAR UNIQUE;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS hyp_internal_deal_id VARCHAR UNIQUE;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS payment_url VARCHAR;

ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS callback_data JSON;

-- Créer les index pour les colonnes HYP
CREATE INDEX IF NOT EXISTS idx_transactions_plan_id 
ON transactions(plan_id);

CREATE INDEX IF NOT EXISTS idx_transactions_hyp_transaction_id 
ON transactions(hyp_transaction_id);

CREATE INDEX IF NOT EXISTS idx_transactions_hyp_internal_deal_id 
ON transactions(hyp_internal_deal_id);

-- ===== Création de la table subscriptions =====

CREATE TABLE IF NOT EXISTS subscriptions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR REFERENCES users(id),
    plan_id VARCHAR,
    license_id VARCHAR,
    product_id INTEGER,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    status VARCHAR,
    next_renewal TIMESTAMP,
    canceled_at TIMESTAMP,
    transaction_id VARCHAR REFERENCES transactions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Créer les index pour la table subscriptions
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
