import json
import unittest
from unittest.mock import MagicMock, patch
from cf_sync.services.github_client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubPermissionError,
)


class TestGitHubClient(unittest.TestCase):
    def setUp(self):
        self.client = GitHubClient(token="ghp_mock_secret_token_12345")

    @patch("urllib.request.urlopen")
    def test_get_authenticated_user(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "login": "Prithviraj173",
            "name": "Prithviraj Adhikary",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        user = self.client.get_authenticated_user()
        self.assertEqual(user["login"], "Prithviraj173")

    @patch("urllib.request.urlopen")
    def test_verify_write_access_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "name": "Project-101",
            "owner": {"login": "RishabhRaj120"},
            "permissions": {"push": True, "pull": True, "admin": False}
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertTrue(self.client.verify_write_access("RishabhRaj120", "Project-101"))

    @patch("urllib.request.urlopen")
    def test_verify_write_access_failure(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "name": "read-only-repo",
            "owner": {"login": "other_owner"},
            "permissions": {"push": False, "pull": True, "admin": False}
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with self.assertRaises(GitHubPermissionError):
            self.client.verify_write_access("other_owner", "read-only-repo")

    @patch("urllib.request.urlopen")
    def test_atomic_commit_bundle(self, mock_urlopen):
        # 1. get_branch_head_commit_sha
        resp_ref = MagicMock()
        resp_ref.status = 200
        resp_ref.read.return_value = json.dumps({"object": {"sha": "head_sha_123"}}).encode("utf-8")
        resp_ref.__enter__.return_value = resp_ref

        # 2. get base commit object
        resp_commit = MagicMock()
        resp_commit.status = 200
        resp_commit.read.return_value = json.dumps({"tree": {"sha": "base_tree_sha_456"}}).encode("utf-8")
        resp_commit.__enter__.return_value = resp_commit

        # 3. create blob 1
        resp_blob1 = MagicMock()
        resp_blob1.status = 201
        resp_blob1.read.return_value = json.dumps({"sha": "blob_sha_1"}).encode("utf-8")
        resp_blob1.__enter__.return_value = resp_blob1

        # 4. create blob 2
        resp_blob2 = MagicMock()
        resp_blob2.status = 201
        resp_blob2.read.return_value = json.dumps({"sha": "blob_sha_2"}).encode("utf-8")
        resp_blob2.__enter__.return_value = resp_blob2

        # 5. create tree
        resp_tree = MagicMock()
        resp_tree.status = 201
        resp_tree.read.return_value = json.dumps({"sha": "new_tree_sha_789"}).encode("utf-8")
        resp_tree.__enter__.return_value = resp_tree

        # 6. create commit
        resp_new_commit = MagicMock()
        resp_new_commit.status = 201
        resp_new_commit.read.return_value = json.dumps({
            "sha": "new_commit_sha_999",
            "html_url": "https://github.com/RishabhRaj120/Project-101/commit/new_commit_sha_999"
        }).encode("utf-8")
        resp_new_commit.__enter__.return_value = resp_new_commit

        # 7. update branch ref
        resp_patch = MagicMock()
        resp_patch.status = 200
        resp_patch.read.return_value = b"{}"
        resp_patch.__enter__.return_value = resp_patch

        mock_urlopen.side_effect = [
            resp_ref,
            resp_commit,
            resp_blob1,
            resp_blob2,
            resp_tree,
            resp_new_commit,
            resp_patch,
        ]

        files = {
            "codeforces/2048-Round/A/solution.cpp": "#include <iostream>",
            "codeforces/2048-Round/A/metadata.json": "{}",
        }

        sha, url = self.client.commit_files_bundle(
            owner="RishabhRaj120",
            repo="Project-101",
            branch="prithvi",
            files_to_commit=files,
            commit_message="Sync Codeforces submissions",
        )

        self.assertEqual(sha, "new_commit_sha_999")
        self.assertEqual(url, "https://github.com/RishabhRaj120/Project-101/commit/new_commit_sha_999")


if __name__ == "__main__":
    unittest.main()
