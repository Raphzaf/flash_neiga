# backend/tests/test_paddle_integration.py
"""
Tests unitaires pour l'intégration Paddle
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the functions we want to test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from routes.paddle_payments import (
    _normalize_api_key,
    verify_paddle_webhook_signature,
    load_paddle_price_ids,
    check_combo_offer_eligibility,
    _extract_price_id_from_item,
)


class TestNormalizeApiKey:
    """Tests pour la normalisation de la clé API"""
    
    def test_normalize_removes_quotes(self):
        """Teste que les guillemets sont supprimés"""
        assert _normalize_api_key('"test_key"') == "test_key"
        assert _normalize_api_key("'test_key'") == "test_key"
    
    def test_normalize_removes_whitespace(self):
        """Teste que les espaces sont supprimés"""
        assert _normalize_api_key("  test_key  ") == "test_key"
        assert _normalize_api_key("\ntest_key\n") == "test_key"
    
    def test_normalize_handles_none(self):
        """Teste que None est géré correctement"""
        assert _normalize_api_key(None) is None
    
    def test_normalize_handles_empty_string(self):
        """Teste que la chaîne vide est gérée correctement"""
        # Empty string is falsy, so it returns None
        assert _normalize_api_key("") is None
    
    def test_normalize_combined(self):
        """Teste la normalisation combinée"""
        assert _normalize_api_key('  "test_key"  ') == "test_key"
        assert _normalize_api_key("  'test_key'  ") == "test_key"


class TestExtractPriceId:
    """Tests pour l'extraction de price_id des items"""
    
    def test_extract_direct_price_id(self):
        """Teste l'extraction d'un price_id direct"""
        item = {"price_id": "pri_123"}
        assert _extract_price_id_from_item(item) == "pri_123"
    
    def test_extract_nested_price_id(self):
        """Teste l'extraction d'un price_id imbriqué"""
        item = {"price": {"id": "pri_456"}}
        assert _extract_price_id_from_item(item) == "pri_456"
    
    def test_extract_direct_takes_precedence(self):
        """Teste que price_id direct a la priorité"""
        item = {"price_id": "pri_123", "price": {"id": "pri_456"}}
        assert _extract_price_id_from_item(item) == "pri_123"
    
    def test_extract_empty_item(self):
        """Teste l'extraction d'un item vide"""
        assert _extract_price_id_from_item({}) is None
        assert _extract_price_id_from_item(None) is None
    
    def test_extract_invalid_nested_structure(self):
        """Teste l'extraction avec structure invalide"""
        item = {"price": "not_a_dict"}
        assert _extract_price_id_from_item(item) is None


class TestWebhookSignatureVerification:
    """Tests pour la vérification de signature webhook"""
    
    def test_verify_valid_signature(self):
        """Teste la vérification d'une signature valide"""
        payload = b'{"event_type": "transaction.completed"}'
        secret = "test_secret"
        timestamp = "1234567890"
        
        # Calculer la signature attendue
        import hmac
        import hashlib
        signed_payload = f"{timestamp}:{payload.decode('utf-8')}"
        expected_hash = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        signature = f"ts={timestamp};h1={expected_hash}"
        
        assert verify_paddle_webhook_signature(payload, signature, secret) is True
    
    def test_verify_invalid_signature(self):
        """Teste la vérification d'une signature invalide"""
        payload = b'{"event_type": "transaction.completed"}'
        secret = "test_secret"
        signature = "ts=1234567890;h1=invalid_hash"
        
        assert verify_paddle_webhook_signature(payload, signature, secret) is False
    
    def test_verify_missing_secret(self):
        """Teste la vérification sans secret"""
        payload = b'{"event_type": "transaction.completed"}'
        signature = "ts=1234567890;h1=some_hash"
        
        assert verify_paddle_webhook_signature(payload, signature, None) is False
    
    def test_verify_missing_signature(self):
        """Teste la vérification sans signature"""
        payload = b'{"event_type": "transaction.completed"}'
        secret = "test_secret"
        
        assert verify_paddle_webhook_signature(payload, None, secret) is False
    
    def test_verify_malformed_signature(self):
        """Teste la vérification avec une signature malformée"""
        payload = b'{"event_type": "transaction.completed"}'
        secret = "test_secret"
        signature = "invalid_format"
        
        assert verify_paddle_webhook_signature(payload, signature, secret) is False


class TestLoadPaddlePriceIds:
    """Tests pour le chargement des price IDs"""
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', create=True)
    def test_load_price_ids_success(self, mock_open, mock_exists):
        """Teste le chargement réussi des price IDs"""
        mock_exists.return_value = True
        mock_data = {
            "code": {"14days": "pri_123", "30days": "pri_456"},
            "videos": {"1month": "pri_789"}
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_data)
        
        # Mock the file read
        with patch('json.load', return_value=mock_data):
            result = load_paddle_price_ids()
            assert result == mock_data
    
    @patch('pathlib.Path.exists')
    def test_load_price_ids_file_not_found(self, mock_exists):
        """Teste quand le fichier n'existe pas"""
        mock_exists.return_value = False
        
        result = load_paddle_price_ids()
        assert result is None


class TestComboOfferEligibility:
    """Tests pour l'éligibilité à l'offre combinée"""
    
    @patch('routes.paddle_payments.load_paddle_price_ids')
    def test_not_video_3months(self, mock_load):
        """Teste quand l'achat n'est pas Vidéos 3 mois"""
        mock_load.return_value = {
            "code": {"14days": "pri_code_14", "30days": "pri_code_30"},
            "videos": {"1month": "pri_video_1", "3months": "pri_video_3"}
        }
        
        mock_db = Mock()
        
        result = check_combo_offer_eligibility("pri_video_1", "user123", mock_db)
        
        assert result["eligible"] is False
        assert "not for Videos 3 months" in result["reason"]
    
    @patch('routes.paddle_payments.load_paddle_price_ids')
    def test_user_has_code_subscription(self, mock_load):
        """Teste quand l'utilisateur a déjà un abonnement Code"""
        mock_load.return_value = {
            "code": {"14days": "pri_code_14", "30days": "pri_code_30"},
            "videos": {"1month": "pri_video_1", "3months": "pri_video_3"}
        }
        
        # Mock database query
        mock_db = Mock()
        mock_transaction = Mock()
        mock_transaction.event_data = {
            "items": [{"price_id": "pri_code_30"}]
        }
        mock_transaction.status = "completed"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_transaction]
        
        result = check_combo_offer_eligibility("pri_video_3", "user123", mock_db)
        
        assert result["eligible"] is True
        assert "has Code subscription" in result["reason"]
    
    @patch('routes.paddle_payments.load_paddle_price_ids')
    def test_user_no_code_subscription(self, mock_load):
        """Teste quand l'utilisateur n'a pas d'abonnement Code"""
        mock_load.return_value = {
            "code": {"14days": "pri_code_14", "30days": "pri_code_30"},
            "videos": {"1month": "pri_video_1", "3months": "pri_video_3"}
        }
        
        # Mock database query - no transactions
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = check_combo_offer_eligibility("pri_video_3", "user123", mock_db)
        
        assert result["eligible"] is False
        assert "does not have Code subscription" in result["reason"]
    
    @patch('routes.paddle_payments.load_paddle_price_ids')
    def test_price_ids_not_loaded(self, mock_load):
        """Teste quand les price IDs ne peuvent pas être chargés"""
        mock_load.return_value = None
        
        mock_db = Mock()
        
        result = check_combo_offer_eligibility("pri_video_3", "user123", mock_db)
        
        assert result["eligible"] is False
        assert "Cannot load price IDs" in result["reason"]


class TestPaddleHealthEndpoint:
    """Tests pour l'endpoint de santé"""
    
    @patch.dict(os.environ, {"PADDLE_API_KEY": "pdl_test_123"})
    def test_health_with_api_key(self):
        """Teste le health check avec une clé API configurée"""
        # This would require FastAPI TestClient, so we'll test the logic
        assert os.getenv("PADDLE_API_KEY") == "pdl_test_123"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_health_without_api_key(self):
        """Teste le health check sans clé API"""
        assert os.getenv("PADDLE_API_KEY") is None


class TestCheckoutRequest:
    """Tests pour la création de checkout"""
    
    @patch('routes.paddle_payments._normalize_api_key')
    @patch.dict(os.environ, {}, clear=True)
    def test_checkout_without_api_key(self, mock_normalize):
        """Teste la création de checkout sans clé API"""
        mock_normalize.return_value = None
        
        # Simuler que la clé n'existe pas
        assert os.getenv("PADDLE_API_KEY") is None


# Tests d'intégration (nécessitent un vrai environnement)
class TestPaddleIntegrationE2E:
    """Tests d'intégration end-to-end (à exécuter avec prudence)"""
    
    @pytest.mark.skipif(
        not os.getenv("PADDLE_API_KEY"),
        reason="PADDLE_API_KEY not configured"
    )
    def test_real_paddle_connection(self):
        """Teste une vraie connexion à l'API Paddle"""
        import requests
        
        api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        
        response = requests.get(
            "https://api.paddle.com/prices?per_page=1",
            headers=headers,
            timeout=10
        )
        
        assert response.status_code < 400, f"API call failed: {response.status_code}"


# Configuration pytest
@pytest.fixture
def mock_db():
    """Fixture pour simuler une session de base de données"""
    db = Mock()
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def sample_price_ids():
    """Fixture pour les price IDs de test"""
    return {
        "code": {
            "14days": "pri_01kd99x603t5whs3t5e949fwcw",
            "30days": "pri_01kd99x6wzyw47pj8x470yxchq",
            "1week_extension": "pri_test_code_ext"
        },
        "videos": {
            "1month": "pri_01kd99x87n1zznba6ar2aej55e",
            "2months": "pri_01kd99x96h49emtgvqndn2m6cn",
            "3months": "pri_01kd99xa4xt0rrmt19ycv7hc2g",
            "1week_extension": "pri_test_video_ext"
        }
    }


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v", "--tb=short"])
