import requests
import sys
import json
from datetime import datetime

class FlashNeigaAPITester:
    def __init__(self, base_url="https://driving-test-prep-8.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.user_id = None
        self.exam_id = None
        self.question_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_register(self):
        """Test user registration"""
        test_user_data = {
            "email": f"testuser_{datetime.now().strftime('%H%M%S')}@example.com",
            "full_name": "Test User",
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data=test_user_data
        )
        
        if success and 'id' in response:
            self.user_id = response['id']
            print(f"   Created user ID: {self.user_id}")
            return True, test_user_data
        return False, {}

    def test_login(self, email, password):
        """Test login and get token"""
        # FastAPI OAuth2PasswordRequestForm expects form data, not JSON
        url = f"{self.base_url}/api/auth/login"
        
        self.tests_run += 1
        print(f"\n🔍 Testing User Login...")
        print(f"   URL: {url}")
        
        try:
            # Use form data instead of JSON for OAuth2PasswordRequestForm
            form_data = {
                "username": email,  # OAuth2 uses 'username' field for email
                "password": password
            }
            
            response = requests.post(url, data=form_data, timeout=10)
            
            success = response.status_code == 200
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                response_data = response.json()
                if 'access_token' in response_data:
                    self.token = response_data['access_token']
                    print(f"   Token received: {self.token[:20]}...")
                    return True
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            print(f"   Token received: {self.token[:20]}...")
            return True
        return False

    def test_seeded_login(self):
        """Test login with seeded user"""
        return self.test_login("test@example.com", "password123")

    def test_get_current_user(self):
        """Test getting current user info"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_get_questions(self):
        """Test getting questions"""
        success, response = self.run_test(
            "Get Questions",
            "GET",
            "questions",
            200
        )
        
        if success and isinstance(response, list) and len(response) > 0:
            self.question_id = response[0]['id']
            print(f"   Found {len(response)} questions, first ID: {self.question_id}")
        
        return success

    def test_create_question(self):
        """Test creating a new question"""
        question_data = {
            "text": "Quelle est la vitesse maximale en ville?",
            "category": "Vitesse",
            "explanation": "La vitesse maximale en ville est de 50 km/h sauf indication contraire.",
            "options": [
                {"text": "30 km/h", "is_correct": False},
                {"text": "50 km/h", "is_correct": True},
                {"text": "70 km/h", "is_correct": False},
                {"text": "90 km/h", "is_correct": False}
            ]
        }
        
        success, response = self.run_test(
            "Create Question",
            "POST",
            "questions",
            200,
            data=question_data
        )
        return success

    def test_get_signs(self):
        """Test getting traffic signs"""
        success, response = self.run_test(
            "Get Traffic Signs",
            "GET",
            "signs",
            200
        )
        return success

    def test_create_sign(self):
        """Test creating a traffic sign"""
        sign_data = {
            "name": "Stop",
            "category": "Obligation",
            "description": "Arrêt obligatoire",
            "image_url": "https://example.com/stop.png"
        }
        
        success, response = self.run_test(
            "Create Traffic Sign",
            "POST",
            "signs",
            200,
            data=sign_data
        )
        return success

    def test_start_exam(self):
        """Test starting an exam"""
        success, response = self.run_test(
            "Start Exam",
            "POST",
            "exam/start",
            200
        )
        
        if success and 'id' in response:
            self.exam_id = response['id']
            print(f"   Started exam ID: {self.exam_id}")
            print(f"   Questions count: {len(response.get('questions', []))}")
        
        return success

    def test_get_exam(self):
        """Test getting exam details"""
        if not self.exam_id:
            print("❌ No exam ID available for testing")
            return False
            
        success, response = self.run_test(
            "Get Exam Details",
            "GET",
            f"exam/{self.exam_id}",
            200
        )
        return success

    def test_submit_answer(self):
        """Test submitting an exam answer"""
        if not self.exam_id or not self.question_id:
            print("❌ No exam ID or question ID available for testing")
            return False
            
        answer_data = {
            "question_id": self.question_id,
            "selected_option_id": "test-option-id"
        }
        
        success, response = self.run_test(
            "Submit Exam Answer",
            "POST",
            f"exam/{self.exam_id}/answer",
            200,
            data=answer_data
        )
        return success

    def test_finish_exam(self):
        """Test finishing an exam"""
        if not self.exam_id:
            print("❌ No exam ID available for testing")
            return False
            
        success, response = self.run_test(
            "Finish Exam",
            "POST",
            f"exam/{self.exam_id}/finish",
            200
        )
        
        if success:
            print(f"   Exam result: {response.get('correct_answers', 0)}/{response.get('total_questions', 0)}")
            print(f"   Passed: {response.get('passed', False)}")
        
        return success

    def test_training_check(self):
        """Test training mode answer checking"""
        if not self.question_id:
            print("❌ No question ID available for testing")
            return False
            
        training_data = {
            "question_id": self.question_id,
            "selected_option_id": "test-option-id"
        }
        
        success, response = self.run_test(
            "Training Answer Check",
            "POST",
            "training/check",
            200,
            data=training_data
        )
        return success

    def test_stats_summary(self):
        """Test getting stats summary"""
        success, response = self.run_test(
            "Stats Summary",
            "GET",
            "stats/summary",
            200
        )
        
        if success:
            print(f"   Recent exams: {len(response.get('recent_exams', []))}")
            print(f"   Total errors: {response.get('total_errors', 0)}")
        
        return success

    def test_stats_activity(self):
        """Test getting activity stats"""
        success, response = self.run_test(
            "Stats Activity",
            "GET",
            "stats/activity",
            200
        )
        return success

def main():
    print("🚀 Starting Flash Neiga API Tests")
    print("=" * 50)
    
    tester = FlashNeigaAPITester()
    
    # Test 1: Try seeded user login first
    print("\n📋 PHASE 1: Authentication Tests")
    seeded_login_success = tester.test_seeded_login()
    
    if not seeded_login_success:
        print("\n⚠️  Seeded user login failed, trying registration...")
        # Test 2: Registration and login
        reg_success, user_data = tester.test_register()
        if reg_success:
            login_success = tester.test_login(user_data['email'], user_data['password'])
            if not login_success:
                print("❌ Registration succeeded but login failed")
                return 1
        else:
            print("❌ Both seeded login and registration failed")
            return 1
    
    # Test 3: Get current user
    tester.test_get_current_user()
    
    # Test 4: Content tests
    print("\n📋 PHASE 2: Content Management Tests")
    tester.test_get_questions()
    tester.test_create_question()
    tester.test_get_signs()
    tester.test_create_sign()
    
    # Test 5: Exam flow tests
    print("\n📋 PHASE 3: Exam Flow Tests")
    exam_started = tester.test_start_exam()
    if exam_started:
        tester.test_get_exam()
        tester.test_submit_answer()
        tester.test_finish_exam()
    
    # Test 6: Training tests
    print("\n📋 PHASE 4: Training Mode Tests")
    tester.test_training_check()
    
    # Test 7: Stats tests
    print("\n📋 PHASE 5: Statistics Tests")
    tester.test_stats_summary()
    tester.test_stats_activity()
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())