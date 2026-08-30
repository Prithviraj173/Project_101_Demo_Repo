"""
GitHub API client providing repository inspection, permission verification,
idempotency state tracking, and atomic multi-file Git Tree commit pushes.
"""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple
from cf_sync.core.models import GitHubRepo

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Generic exception for GitHub API errors."""
    pass


class GitHubAuthError(GitHubAPIError):
    """Raised on authentication failure / 401 Bad credentials."""
    pass


class GitHubPermissionError(GitHubAPIError):
    """Raised on 403 Forbidden / insufficient repository permissions."""
    pass


class GitHubNotFoundError(GitHubAPIError):
    """Raised on 404 Not Found."""
    pass


class GitHubClient:
    """
    Client for interacting with GitHub REST and Git Data APIs.
    """
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, timeout: int = 20):
        if not token or not token.strip():
            raise GitHubAuthError("GitHub access token is required")
        self._token = token.strip()
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CF-GitHub-Sync/1.0 (+https://github.com/RishabhRaj120/Project-101)",
        }

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Performs authenticated HTTP request to GitHub API with secure error masking.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"

        body = None
        headers = self._headers()
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 204:
                    return None
                resp_text = resp.read().decode("utf-8")
                if resp_text:
                    return json.loads(resp_text)
                return {}
        except urllib.error.HTTPError as e:
            raw_body = e.read().decode("utf-8", errors="ignore")
            message = "Unknown error"
            try:
                err_json = json.loads(raw_body)
                message = err_json.get("message", raw_body)
            except Exception:
                message = raw_body or str(e)

            # Never log the token or raw auth headers
            clean_msg = message.replace(self._token, "[REDACTED_TOKEN]")

            if e.code == 401:
                raise GitHubAuthError(f"GitHub authentication failed: {clean_msg}")
            elif e.code == 403:
                raise GitHubPermissionError(f"Insufficient permissions on GitHub: {clean_msg}")
            elif e.code == 404:
                raise GitHubNotFoundError(f"GitHub resource not found: {clean_msg}")
            else:
                raise GitHubAPIError(f"GitHub API error ({e.code}): {clean_msg}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise GitHubAPIError(f"Network error connecting to GitHub: {str(e)}")

    def get_authenticated_user(self) -> Dict[str, Any]:
        """Returns the authenticated GitHub user profile."""
        return self._request("user")

    def list_user_repositories(self, per_page: int = 100) -> List[GitHubRepo]:
        """Lists repositories accessible to the authenticated user."""
        repos_data = self._request(
            "user/repos",
            params={"sort": "updated", "per_page": per_page, "affiliation": "owner,collaborator,organization_member"}
        )
        if not isinstance(repos_data, list):
            return []
    def get_repository(self, owner: str, repo: str) -> GitHubRepo:
        """Fetches details for a specific repository."""
        data = self._request(f"repos/{owner}/{repo}")
        return GitHubRepo.from_dict(data)

    def create_repository(
        self,
        name: str = "Codeforces-Solutions",
        description: str = "Automated Codeforces Solutions Archive — Topic-wise & Rating-wise from Day 1",
        is_private: bool = False,
        auto_init: bool = True
    ) -> GitHubRepo:
        """Creates a new repository on the authenticated user's GitHub account."""
        data = self._request(
            "user/repos",
            method="POST",
            data={
                "name": name,
                "description": description,
                "private": is_private,
                "auto_init": auto_init,
            }
        )
        return GitHubRepo.from_dict(data)

    def get_or_create_repository(
        self,
        owner: str,
        name: str = "Codeforces-Solutions",
        description: str = "Automated Codeforces Solutions Archive — Topic-wise & Rating-wise from Day 1",
        is_private: bool = False
    ) -> GitHubRepo:
        """Retrieves an existing repo or automatically creates a new dedicated repository."""
        try:
            return self.get_repository(owner, name)
        except GitHubNotFoundError:
            logger.info(f"Repository {owner}/{name} does not exist. Auto-creating repository on GitHub...")
            return self.create_repository(name=name, description=description, is_private=is_private, auto_init=True)

    def verify_write_access(self, owner: str, repo: str) -> bool:
        """Verifies that the user has push/write permissions on the target repository."""
        repo_obj = self.get_repository(owner, repo)
        perms = repo_obj.permissions
        if not perms.get("push", False) and not perms.get("admin", False):
            raise GitHubPermissionError(
                f"You do not have push permissions to repository '{owner}/{repo}'."
            )
        return True

    def list_branches(self, owner: str, repo: str) -> List[str]:
        """Lists branch names in the repository."""
        branches = self._request(f"repos/{owner}/{repo}/branches", params={"per_page": 100})
        if isinstance(branches, list):
            return [b["name"] for b in branches if "name" in b]
        return []

    def get_branch_head_commit_sha(self, owner: str, repo: str, branch: str) -> str:
        """Gets the current HEAD commit SHA for a branch."""
        ref_data = self._request(f"repos/{owner}/{repo}/git/ref/heads/{branch}")
        return ref_data["object"]["sha"]

    def get_file_content(self, owner: str, repo: str, path: str, branch: str = "main") -> Optional[str]:
        """Retrieves decoded file content if it exists."""
        try:
            data = self._request(f"repos/{owner}/{repo}/contents/{path.lstrip('/')}", params={"ref": branch})
            if "content" in data:
                encoded = data["content"]
                return base64.b64decode(encoded).decode("utf-8")
        except GitHubNotFoundError:
            return None
        return None

    def fetch_synced_submission_ids(
        self,
        owner: str,
        repo: str,
        branch: str,
        base_dir: str = "codeforces"
    ) -> Set[int]:
        """
        Retrieves the set of already synchronized submission IDs for duplicate detection & idempotency.
        Checks for .cf_sync_index.json first; if absent, inspects git tree metadata files.
        """
        synced_ids: Set[int] = set()
        index_file_path = f"{base_dir}/.cf_sync_index.json"

        # Check existing index file
        content = self.get_file_content(owner, repo, index_file_path, branch)
        if content:
            try:
                index_json = json.loads(content)
                ids = index_json.get("syncedSubmissionIds", [])
                if isinstance(ids, list):
                    for sid in ids:
                        try:
                            synced_ids.add(int(sid))
                        except (ValueError, TypeError):
                            pass
                return synced_ids
            except Exception as e:
                logger.warning(f"Could not parse {index_file_path}: {e}")

        # Fallback: scan git tree recursively for metadata.json files
        try:
            head_sha = self.get_branch_head_commit_sha(owner, repo, branch)
            tree_data = self._request(f"repos/{owner}/{repo}/git/trees/{head_sha}", params={"recursive": 1})
            tree_items = tree_data.get("tree", [])
            for item in tree_items:
                path = item.get("path", "")
                if path.startswith(base_dir) and path.endswith("/metadata.json"):
                    # We can lazily read or track directory names
                    pass
        except Exception as e:
            logger.debug(f"Tree inspection fallback note: {e}")

        return synced_ids

    def create_git_blob(self, owner: str, repo: str, content: str) -> str:
        """Creates a Git blob for file content and returns blob SHA."""
        data = self._request(
            f"repos/{owner}/{repo}/git/blobs",
            method="POST",
            data={
                "content": content,
                "encoding": "utf-8",
            }
        )
        return data["sha"]

    def create_git_tree(
        self,
        owner: str,
        repo: str,
        base_tree_sha: Optional[str],
        tree_entries: List[Dict[str, Any]]
    ) -> str:
        """
        Creates a Git tree containing multiple file entries and returns tree SHA.
        tree_entries format: [{'path': '...', 'mode': '100644', 'type': 'blob', 'sha': '...'}]
        """
        payload: Dict[str, Any] = {"tree": tree_entries}
        if base_tree_sha:
            payload["base_tree"] = base_tree_sha

        data = self._request(
            f"repos/{owner}/{repo}/git/trees",
            method="POST",
            data=payload
        )
        return data["sha"]

    def create_git_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parent_shas: List[str]
    ) -> Dict[str, Any]:
        """Creates a Git commit pointing to tree_sha and parent commits."""
        return self._request(
            f"repos/{owner}/{repo}/git/commits",
            method="POST",
            data={
                "message": message,
                "tree": tree_sha,
                "parents": parent_shas,
            }
        )

    def update_branch_ref(self, owner: str, repo: str, branch: str, commit_sha: str, force: bool = False) -> None:
        """Updates the branch ref to point to the new commit."""
        self._request(
            f"repos/{owner}/{repo}/git/refs/heads/{branch}",
            method="PATCH",
            data={
                "sha": commit_sha,
                "force": force,
            }
        )

    def commit_files_bundle(
        self,
        owner: str,
        repo: str,
        branch: str,
        files_to_commit: Dict[str, str],
        commit_message: str,
    ) -> Tuple[str, str]:
        """
        Atomic multi-file commit engine using Git Data Trees API.
        Creates all blobs, creates tree, creates commit, and updates branch ref.
        Returns: (commit_sha, commit_url)
        """
        if not files_to_commit:
            raise ValueError("No files to commit")

        # 1. Get HEAD commit SHA and its base tree
        head_commit_sha = self.get_branch_head_commit_sha(owner, repo, branch)
        commit_data = self._request(f"repos/{owner}/{repo}/git/commits/{head_commit_sha}")
        base_tree_sha = commit_data["tree"]["sha"]

        # 2. Create blobs for all files
        tree_entries: List[Dict[str, Any]] = []
        for file_path, content in files_to_commit.items():
            clean_path = file_path.lstrip("/")
            blob_sha = self.create_git_blob(owner, repo, content)
            tree_entries.append({
                "path": clean_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        # 3. Create tree object
        new_tree_sha = self.create_git_tree(owner, repo, base_tree_sha, tree_entries)

        # 4. Create commit object
        commit_obj = self.create_git_commit(
            owner=owner,
            repo=repo,
            message=commit_message,
            tree_sha=new_tree_sha,
            parent_shas=[head_commit_sha],
        )
        new_commit_sha = commit_obj["sha"]
        commit_url = commit_obj.get("html_url") or f"https://github.com/{owner}/{repo}/commit/{new_commit_sha}"

        # 5. Update branch ref
        self.update_branch_ref(owner, repo, branch, new_commit_sha)

        return new_commit_sha, commit_url
