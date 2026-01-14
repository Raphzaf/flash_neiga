#!/usr/bin/env python3
"""
Test script for HYP payment integration
Tests configuration, payment creation, and API connectivity
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv

# Load environment variables
env_path = backend_path / ".env"
if env_path.exists():
    load_dotenv(env_path)

# HYP Configuration
HYP_TERMINAL_ID = os.environ.get("HYP_TERMINAL_ID", "4502176330")
HYP_USER_ID = os.environ.get("HYP_USER_ID", "pveda")
HYP_API_KEY = os.environ.get("HYP_API_KEY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_config():
    """Test HYP configuration"""
    print_section("1. Testing HYP Configuration")
    
    print(f"Terminal ID: {HYP_TERMINAL_ID}")
    print(f"User ID: {HYP_USER_ID}")
    
    # Show API key preview instead of just "Set"
    if HYP_API_KEY:
        api_key_preview = HYP_API_KEY[:10] + "..." if len(HYP_API_KEY) > 10 else HYP_API_KEY
        print(f"API Key: {api_key_preview} (length: {len(HYP_API_KEY)})")
    else:
        print(f"API Key: ✗ Not Set")
    
    print(f"Backend URL: {BACKEND_URL}")
    
    # Display more config details
    print(f"\nURL Configuration:")
    success_url = os.environ.get("HYP_SUCCESS_URL", "https://app.flash-neiga.com/payment/success")
    error_url = os.environ.get("HYP_ERROR_URL", "https://app.flash-neiga.com/payment/failure")
    callback_url = os.environ.get("HYP_CALLBACK_URL", "http://localhost:8000/api/payments/hyp/callback")
    print(f"  Success URL: {success_url}")
    print(f"  Error URL: {error_url}")
    print(f"  Callback URL: {callback_url}")
    
    if not HYP_API_KEY:
        print("\n⚠️  WARNING: HYP_API_KEY is not set!")
        print("   Set it in backend/.env or environment variables")
        return False
    
    print("\n✓ Configuration looks good!")
    return True


def test_verify_endpoint():
    """Test the verify-config endpoint"""
    print_section("2. Testing Verify Config Endpoint")
    
    try:
        url = f"{BACKEND_URL}/api/payments/hyp/verify-config"
        print(f"GET {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ Verify endpoint successful!")
            print(f"   Configured: {data.get('hyp_configured')}")
            print(f"   Plans loaded: {data.get('plans_loaded')}")
            print(f"   Available plans: {', '.join(data.get('available_plans', []))}")
            return True
        else:
            print(f"\n✗ Verify endpoint failed: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"\n✗ Failed to connect to backend: {e}")
        print("   Make sure the backend server is running:")
        print("   cd backend && uvicorn server:app --reload")
        return False


def test_get_plans():
    """Test getting available plans"""
    print_section("3. Testing Get Plans Endpoint")
    
    try:
        url = f"{BACKEND_URL}/api/payments/hyp/plans"
        print(f"GET {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            plans = data.get("plans", {})
            
            print(f"\n✓ Found {len(plans)} plans:")
            for plan_id, plan_info in plans.items():
                print(f"\n   {plan_id}:")
                print(f"     Name: {plan_info.get('name')}")
                print(f"     Amount: {plan_info.get('amount')} {plan_info.get('currency')}")
                print(f"     Duration: {plan_info.get('duration_days')} days")
                print(f"     Type: {plan_info.get('type')}")
                # Check for is_extension flag
                if plan_info.get('is_extension'):
                    print(f"     Extension: Yes")
            
            return True
        else:
            print(f"\n✗ Get plans failed: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"\n✗ Failed to get plans: {e}")
        return False


def test_create_payment(plan_id="code_14d"):
    """Test creating a payment"""
    print_section(f"4. Testing Create Payment (Plan: {plan_id})")
    
    try:
        url = f"{BACKEND_URL}/api/payments/hyp/create-payment"
        print(f"POST {url}")
        
        payload = {
            "plan_id": plan_id,
            "user_email": "test@example.com"
        }
        
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n✓ Payment created successfully!")
            print(f"   Transaction ID: {data.get('transaction_id')}")
            print(f"   Amount: {data.get('amount')} {data.get('currency')}")
            print(f"   Payment URL: {data.get('payment_url')[:80]}...")
            print("\n   ⚠️  This is a test transaction. To complete it:")
            print(f"      1. Open the payment URL in a browser")
            print(f"      2. Use HYP test card details")
            print(f"      3. Check callback at {BACKEND_URL}/api/payments/hyp/callback")
            
            return True, data.get('transaction_id')
        else:
            print(f"\n✗ Create payment failed: {response.status_code}")
            print(f"   {response.text}")
            return False, None
            
    except requests.RequestException as e:
        print(f"\n✗ Failed to create payment: {e}")
        return False, None


def test_get_transaction(transaction_id):
    """Test getting transaction details"""
    print_section(f"5. Testing Get Transaction (ID: {transaction_id})")
    
    try:
        url = f"{BACKEND_URL}/api/payments/hyp/transaction/{transaction_id}"
        print(f"GET {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n✓ Transaction retrieved successfully!")
            print(f"   Status: {data.get('status')}")
            print(f"   Plan: {data.get('plan_id')}")
            print(f"   Amount: {data.get('amount')} {data.get('currency')}")
            print(f"   Created: {data.get('created_at')}")
            
            # Show subscription details if available
            if 'subscription' in data:
                sub = data['subscription']
                print(f"\n   Subscription:")
                print(f"     ID: {sub.get('id')}")
                print(f"     Plan: {sub.get('plan_name')} ({sub.get('plan_id')})")
                print(f"     Status: {sub.get('status')}")
                print(f"     Start: {sub.get('start_date')}")
                print(f"     End: {sub.get('end_date')}")
            
            return True
        else:
            print(f"\n✗ Get transaction failed: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"\n✗ Failed to get transaction: {e}")
        return False


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("  HYP Payment Integration Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: Configuration
    results.append(("Configuration", test_config()))
    
    # Test 2: Verify endpoint
    results.append(("Verify Config", test_verify_endpoint()))
    
    # Test 3: Get plans
    results.append(("Get Plans", test_get_plans()))
    
    # Test 4: Create payment
    success, transaction_id = test_create_payment()
    results.append(("Create Payment", success))
    
    # Test 5: Get transaction (if payment was created)
    if transaction_id:
        results.append(("Get Transaction", test_get_transaction(transaction_id)))
    
    # Print summary
    print_section("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        print("\n" + "=" * 60)
        print("  Next Steps")
        print("=" * 60)
        print("\n1. Complete a test transaction:")
        print("   - Open the payment URL in a browser")
        print("   - Use HYP test credit card:")
        print("     Card: 4580458045804580")
        print("     CVV: 123")
        print("     Expiry: Any future date")
        print("\n2. Verify callback is received:")
        print(f"   - Check logs at {BACKEND_URL}")
        print("   - Callback should be sent to /api/payments/hyp/callback")
        print("\n3. Check subscription creation:")
        print("   - Transaction status should become 'completed'")
        print("   - Subscription should be created with correct dates")
        print("\n4. Test success page:")
        print("   - Should redirect to success page")
        print("   - Should display subscription details")
        print("\n5. Production deployment:")
        print("   - Set HYP_API_KEY in Render")
        print("   - Update callback URL in HYP dashboard")
        print("   - Verify production URLs are correct")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
