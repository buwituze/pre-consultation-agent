import unittest
from backend.utils.session_logger import log_session_event
from backend.routers.auth import authenticate_user

class TestUtils(unittest.TestCase):
    def test_log_session_event_returns_expected_string(self):
        result = log_session_event('user1', 'login')
        self.assertIn('user1', result)
        self.assertIn('login', result)

class TestAuth(unittest.TestCase):
    def test_authenticate_user_invalid(self):
        response = authenticate_user('invalid_user', 'wrong_password')
        self.assertFalse(response['success'])

if __name__ == '__main__':
    unittest.main()
