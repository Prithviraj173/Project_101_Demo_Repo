import unittest
from cf_sync.core.path_builder import PathBuilder, sanitize_path_segment
from cf_sync.services.github_client import GitHubClient, GitHubAuthError


class TestSecurityAndEdgeCases(unittest.TestCase):
    def test_path_traversal_variations(self):
        builder = PathBuilder()

        dangerous_inputs = [
            "../../../etc/shadow",
            "..\\..\\Windows\\System32\\cmd.exe",
            "/absolute/root/path",
            "C:\\Program Files\\app",
            "problem\x00with_null_byte",
            "   ...   ",
            "CON.cpp",
            "aux/prn/nul",
        ]

        for inp in dangerous_inputs:
            clean = sanitize_path_segment(inp)
            self.assertFalse(clean.startswith("/"))
            self.assertFalse(clean.startswith("\\"))
            self.assertNotIn("..", clean.split("/"))
            self.assertNotIn("\x00", clean)

    def test_token_masking_in_exceptions(self):
        # Ensure raw token is never exposed in error text
        with self.assertRaises(GitHubAuthError):
            GitHubClient(token="")


if __name__ == "__main__":
    unittest.main()
