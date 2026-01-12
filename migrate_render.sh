#!/bin/bash
# Script d'aide pour exécuter la migration sur Render
# Usage: bash migrate_render.sh

echo "🔄 HYP Database Migration Helper"
echo "=================================="
echo ""
echo "📋 Steps to run migration on Render:"
echo ""
echo "1. Go to https://dashboard.render.com"
echo "2. Select your backend service (flash-neiga-backend)"
echo "3. Click 'Shell' in the left menu"
echo "4. Run the following commands:"
echo ""
echo "   pip install psycopg2-binary"
echo "   python backend/migrations/run_migration.py"
echo ""
echo "5. Type 'yes' when prompted"
echo "6. Wait for confirmation message"
echo "7. Go back to dashboard and click 'Manual Deploy' -> 'Clear build cache & deploy'"
echo ""
echo "✅ After migration, test the payment flow!"
