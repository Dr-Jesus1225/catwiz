"""Unit tests for privacy-safe CatWiz log redaction."""

import unittest

from catwiz.logging_redaction import redact_mapping, redact_text


class RedactionTests(unittest.TestCase):
    def test_cookie_and_authorization_headers_are_fully_redacted(self):
        source = "Cookie: sid=private; preference=private-too\nAuthorization: Bearer secret-token"
        result = redact_text(source)
        self.assertNotIn("private", result)
        self.assertNotIn("secret-token", result)
        self.assertIn("Cookie: [REDACTED]", result)
        self.assertIn("Authorization: [REDACTED]", result)

    def test_secret_assignments_are_redacted(self):
        result = redact_text("api_token=abc123 password=hunter2")
        self.assertNotIn("abc123", result)
        self.assertNotIn("hunter2", result)

    def test_url_credentials_and_query_values_are_removed(self):
        result = redact_text("https://user:password@example.test/video?token=abc&v=123")
        self.assertNotIn("user", result)
        self.assertNotIn("password", result)
        self.assertNotIn("abc", result)
        self.assertNotIn("123", result)
        self.assertIn("example.test/video", result)

    def test_mapping_redacts_secret_fields(self):
        result = redact_mapping({
            "cookies": "session=private",
            "format": "best",
            "headers": {"Authorization": "Bearer secret"},
        })
        self.assertEqual(result["cookies"], "[REDACTED]")
        self.assertEqual(result["format"], "best")
        self.assertEqual(result["headers"]["Authorization"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
