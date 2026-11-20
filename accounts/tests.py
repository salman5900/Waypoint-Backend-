from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import EmailOTP
from accounts.services import request_email_otp

User = get_user_model()


class ClassicAuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth-register')
        self.login_url = reverse('auth-login')
        self.me_url = reverse('auth-me')

    def test_register_user_success(self):
        payload = {
            "username": "wanderlust_john",
            "email": "john@example.com",
            "password": "SuperSecretPassword123!",
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["username"], "wanderlust_john")
        self.assertEqual(data["user"]["email"], "john@example.com")
        self.assertTrue(User.objects.filter(email="john@example.com").exists())

    def test_register_duplicate_email(self):
        User.objects.create_user(username="first_user", email="test@example.com", password="password123")
        payload = {
            "username": "second_user",
            "email": "test@example.com",
            "password": "password123",
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "USER_ALREADY_EXISTS")

    def test_register_duplicate_username(self):
        User.objects.create_user(username="wanderer", email="user1@example.com", password="password123")
        payload = {
            "username": "wanderer",
            "email": "user2@example.com",
            "password": "password123",
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "USER_ALREADY_EXISTS")

    def test_register_password_too_short(self):
        payload = {
            "username": "short_pass",
            "email": "short@example.com",
            "password": "123",
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_login_with_username_success(self):
        User.objects.create_user(username="alice", email="alice@example.com", password="SecurePassword123!")
        payload = {
            "identifier": "alice",
            "password": "SecurePassword123!",
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertEqual(response.data["data"]["user"]["username"], "alice")

    def test_login_with_email_success(self):
        User.objects.create_user(username="bob", email="bob@example.com", password="SecurePassword123!")
        payload = {
            "identifier": "bob@example.com",
            "password": "SecurePassword123!",
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertEqual(response.data["data"]["user"]["email"], "bob@example.com")

    def test_login_invalid_password(self):
        User.objects.create_user(username="carol", email="carol@example.com", password="CorrectPassword123!")
        payload = {
            "identifier": "carol@example.com",
            "password": "WrongPassword",
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "AUTHENTICATION_FAILED")

    def test_login_nonexistent_user(self):
        payload = {
            "identifier": "ghost@example.com",
            "password": "SomePassword123!",
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "AUTHENTICATION_FAILED")


class EmailOTPAuthTests(APITestCase):
    def setUp(self):
        self.request_otp_url = reverse('auth-request-otp')
        self.verify_otp_url = reverse('auth-verify-otp')
        self.me_url = reverse('auth-me')

    def test_request_otp_success_and_email_dispatched(self):
        email = "traveler@example.com"
        response = self.client.post(self.request_otp_url, {"email": email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["email"], email)

        # Check DB record
        self.assertEqual(EmailOTP.objects.filter(email=email).count(), 1)
        otp = EmailOTP.objects.get(email=email)
        self.assertFalse(otp.is_used)
        self.assertNotEqual(otp.code_hash, "")  # Hashed, never plaintext

        # Check outbox email
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [email])
        self.assertIn("Your Waypoint Verification Code", mail.outbox[0].subject)

    def test_request_otp_invalidates_prior_unused_otps(self):
        email = "frequent@example.com"
        self.client.post(self.request_otp_url, {"email": email}, format='json')
        self.client.post(self.request_otp_url, {"email": email}, format='json')

        unused = EmailOTP.objects.filter(email=email, is_used=False)
        self.assertEqual(unused.count(), 1)
        used = EmailOTP.objects.filter(email=email, is_used=True)
        self.assertEqual(used.count(), 1)

    @patch('secrets.randbelow', return_value=123456)
    def test_verify_otp_new_user_auto_signup(self, mock_rand):
        email = "newbie@example.com"
        # Request OTP
        self.client.post(self.request_otp_url, {"email": email}, format='json')

        # Verify OTP
        response = self.client.post(self.verify_otp_url, {"email": email, "code": "123456"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertTrue(data["isNewUser"])
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["email"], email)
        self.assertTrue(data["user"]["username"].startswith("newbie_"))

        # Check OTP is now used
        otp = EmailOTP.objects.get(email=email)
        self.assertTrue(otp.is_used)

    @patch('secrets.randbelow', return_value=654321)
    def test_verify_otp_existing_user_login(self, mock_rand):
        email = "existing@example.com"
        User.objects.create_user(username="veteran", email=email, password="password123")

        self.client.post(self.request_otp_url, {"email": email}, format='json')
        response = self.client.post(self.verify_otp_url, {"email": email, "code": "654321"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertFalse(data["isNewUser"])
        self.assertEqual(data["user"]["username"], "veteran")

    @patch('secrets.randbelow', return_value=999999)
    def test_verify_otp_wrong_code(self, mock_rand):
        email = "wrong_code@example.com"
        self.client.post(self.request_otp_url, {"email": email}, format='json')

        response = self.client.post(self.verify_otp_url, {"email": email, "code": "111111"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "INVALID_OTP")

        otp = EmailOTP.objects.get(email=email)
        self.assertEqual(otp.attempts, 1)
        self.assertFalse(otp.is_used)

    @patch('secrets.randbelow', return_value=888888)
    def test_verify_otp_max_attempts_lockout(self, mock_rand):
        email = "lockout@example.com"
        self.client.post(self.request_otp_url, {"email": email}, format='json')

        # 5 wrong attempts
        for i in range(5):
            resp = self.client.post(self.verify_otp_url, {"email": email, "code": "000000"}, format='json')
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 6th attempt should be locked out
        resp = self.client.post(self.verify_otp_url, {"email": email, "code": "888888"}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(resp.data["error"]["code"], ["OTP_MAX_ATTEMPTS_EXCEEDED", "OTP_NOT_FOUND"])

    @patch('secrets.randbelow', return_value=777777)
    def test_verify_otp_expired(self, mock_rand):
        email = "expired@example.com"
        self.client.post(self.request_otp_url, {"email": email}, format='json')

        # Artificially expire the OTP
        otp = EmailOTP.objects.get(email=email)
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=['expires_at'])

        response = self.client.post(self.verify_otp_url, {"email": email, "code": "777777"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "OTP_EXPIRED")

    @patch('secrets.randbelow', return_value=555555)
    def test_verify_otp_reused_rejected(self, mock_rand):
        email = "reused@example.com"
        self.client.post(self.request_otp_url, {"email": email}, format='json')

        # 1st verification succeeds
        resp1 = self.client.post(self.verify_otp_url, {"email": email, "code": "555555"}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # 2nd verification must fail
        resp2 = self.client.post(self.verify_otp_url, {"email": email, "code": "555555"}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp2.data["error"]["code"], "OTP_NOT_FOUND")


class ProtectedMeEndpointTests(APITestCase):
    def setUp(self):
        self.me_url = reverse('auth-me')
        self.user = User.objects.create_user(
            username="voyager",
            email="voyager@example.com",
            password="Password123!"
        )

    def test_me_without_token_unauthorized(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "NOT_AUTHENTICATED")

    def test_me_with_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token-string")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])

    def test_me_with_valid_token(self):
        login_url = reverse('auth-login')
        login_resp = self.client.post(login_url, {"identifier": "voyager", "password": "Password123!"}, format='json')
        token = login_resp.data["data"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["username"], "voyager")
        self.assertEqual(response.data["data"]["email"], "voyager@example.com")
