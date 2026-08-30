"""
REST API and Web Server for Codeforces to GitHub Sync.
Provides endpoints for frontend, CLI, and extension integrations.
"""
import argparse
import json
import logging
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, Optional

from cf_sync.core.models import SyncConfig, SyncFilter, VerdictMode
from cf_sync.services.codeforces_client import CodeforcesClient, CodeforcesHandleNotFoundError
from cf_sync.services.github_client import GitHubClient, GitHubAuthError, GitHubPermissionError
from cf_sync.services.sync_service import SyncService

logger = logging.getLogger(__name__)

# In-memory storage for asynchronous sync jobs
SYNC_JOBS: Dict[str, Dict[str, Any]] = {}
SYNC_JOBS_LOCK = threading.Lock()


class SyncAPIHandler(SimpleHTTPRequestHandler):
    """
    HTTP Request Handler handling REST API routes and serving the web dashboard.
    """

    def __init__(self, *args, web_dir: Optional[str] = None, **kwargs):
        self.web_dir = web_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
        super().__init__(*args, **kwargs)

    def _send_json(self, status_code: int, data: Any):
        payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, status_code: int, message: str, details: Optional[Any] = None):
        self._send_json(status_code, {
            "success": False,
            "error": message,
            "details": details,
        })

    def _read_json_body(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len <= 0:
            return {}
        body = self.rfile.read(content_len).decode("utf-8")
        return json.loads(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health check
        if path == "/api/health":
            self._send_json(200, {"status": "ok", "version": "1.0.0", "timeUtc": datetime.now(timezone.utc).isoformat()})
            return

        # Codeforces submissions preview
        if path == "/api/codeforces/submissions":
            handle = query.get("handle", [""])[0].strip()
            if not handle:
                self._send_error_json(400, "Query parameter 'handle' is required")
                return

            limit_val = query.get("limit", ["50"])[0].strip()
            limit = int(limit_val) if limit_val.isdigit() and int(limit_val) > 0 else None
            is_own = query.get("is_own_account", ["false"])[0].lower() == "true"
            sort_order = query.get("sort", ["asc"])[0].lower()

            try:
                cf = CodeforcesClient()
                submissions = cf.fetch_all_submissions(handle=handle, max_submissions=limit, is_own_account=is_own)
                
                # Sort submissions: 'asc' for Day 1 (oldest) first, 'desc' for newest first
                if sort_order == "asc":
                    submissions.sort(key=lambda s: s.creation_time_seconds)
                else:
                    submissions.sort(key=lambda s: s.creation_time_seconds, reverse=True)

                self._send_json(200, {
                    "success": True,
                    "handle": handle,
                    "count": len(submissions),
                    "sort": sort_order,
                    "submissions": [s.to_dict() for s in submissions]
                })
            except Exception as e:
                self._send_error_json(500, f"Failed to fetch submissions: {str(e)}")
            return

        # GitHub branches
        if path == "/api/github/branches":
            token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
            if not token:
                token = query.get("token", [""])[0].strip()
            owner = query.get("owner", [""])[0].strip()
            repo = query.get("repo", [""])[0].strip()

            if not token or not owner or not repo:
                self._send_error_json(400, "Missing required parameters: token, owner, repo")
                return

            try:
                gh = GitHubClient(token=token)
                branches = gh.list_branches(owner, repo)
                self._send_json(200, {"success": True, "branches": branches})
            except Exception as e:
                self._send_error_json(500, str(e))
            return

        # Sync job status by ID
        if path.startswith("/api/codeforces/sync/"):
            job_id = path.split("/")[-1]
            with SYNC_JOBS_LOCK:
                job = SYNC_JOBS.get(job_id)
            if not job:
                self._send_error_json(404, f"Sync job '{job_id}' not found")
                return
            self._send_json(200, {"success": True, "job": job})
            return

        # Serve static web frontend files
        self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_json_body()
        except Exception as e:
            self._send_error_json(400, f"Invalid JSON payload: {str(e)}")
            return

        # Codeforces connect / validate handle
        if path == "/api/codeforces/connect":
            handle = body.get("handle", "").strip()
            if not handle:
                self._send_error_json(400, "Handle is required")
                return

            try:
                cf = CodeforcesClient(
                    api_key=body.get("apiKey"),
                    api_secret=body.get("apiSecret")
                )
                user_info = cf.validate_handle(handle)
                self._send_json(200, {
                    "success": True,
                    "handle": user_info.get("handle"),
                    "rating": user_info.get("rating"),
                    "rank": user_info.get("rank"),
                    "maxRating": user_info.get("maxRating"),
                    "titlePhoto": user_info.get("titlePhoto"),
                    "avatar": user_info.get("avatar"),
                    "organization": user_info.get("organization"),
                })
            except CodeforcesHandleNotFoundError as e:
                self._send_error_json(404, str(e))
            except Exception as e:
                self._send_error_json(500, f"Codeforces validation failed: {str(e)}")
            return

        # GitHub connect / list repos
        if path == "/api/github/connect":
            token = body.get("token", "").strip()
            if not token:
                self._send_error_json(400, "GitHub access token is required")
                return

            try:
                gh = GitHubClient(token=token)
                user = gh.get_authenticated_user()
                repos = gh.list_user_repositories(per_page=100)

                self._send_json(200, {
                    "success": True,
                    "user": {
                        "login": user.get("login"),
                        "name": user.get("name"),
                        "avatarUrl": user.get("avatar_url"),
                        "htmlUrl": user.get("html_url"),
                    },
                    "repos": [
                        {
                            "name": r.name,
                            "owner": r.owner,
                            "fullName": r.full_name,
                            "defaultBranch": r.default_branch,
                            "isPrivate": r.is_private,
                            "canPush": r.permissions.get("push", False) or r.permissions.get("admin", False),
                        }
                        for r in repos
                    ]
                })
            except GitHubAuthError as e:
                self._send_error_json(401, str(e))
            except Exception as e:
                self._send_error_json(500, f"GitHub connection failed: {str(e)}")
            return

        # Trigger Codeforces to GitHub Sync
        if path == "/api/codeforces/sync":
            handle = body.get("handle", "").strip()
            token = body.get("githubToken", "").strip()
            repo_owner = body.get("repoOwner", "").strip()
            repo_name = body.get("repoName", "").strip()

            if not handle or not token or not repo_owner or not repo_name:
                self._send_error_json(400, "Missing required parameters: handle, githubToken, repoOwner, repoName")
                return

            branch = body.get("branch", "main").strip()
            dest_dir = body.get("destinationDir", "codeforces").strip()
            commit_msg = body.get("commitMessage")
            is_own = bool(body.get("isOwnAccount", False))
            cf_key = body.get("cfApiKey")
            cf_secret = body.get("cfApiSecret")

            # Parse filter options
            filter_data = body.get("filter", {})
            v_mode_str = filter_data.get("verdictMode", "ALL")
            try:
                v_mode = VerdictMode(v_mode_str)
            except ValueError:
                v_mode = VerdictMode.ALL

            after_dt = None
            if filter_data.get("afterDate"):
                try:
                    after_dt = datetime.fromisoformat(filter_data["afterDate"].replace("Z", "+00:00"))
                except Exception:
                    pass

            before_dt = None
            if filter_data.get("beforeDate"):
                try:
                    before_dt = datetime.fromisoformat(filter_data["beforeDate"].replace("Z", "+00:00"))
                except Exception:
                    pass

            cid = None
            if filter_data.get("contestId"):
                try:
                    cid = int(filter_data["contestId"])
                except Exception:
                    pass

            lim = None
            if filter_data.get("limit"):
                try:
                    lim = int(filter_data["limit"])
                except Exception:
                    pass

            sync_filter = SyncFilter(
                verdict_mode=v_mode,
                custom_verdict=filter_data.get("customVerdict"),
                after_date=after_dt,
                before_date=before_dt,
                contest_id=cid,
                problem_index=filter_data.get("problemIndex"),
                problem_tag=filter_data.get("problemTag"),
                language=filter_data.get("language"),
                limit=lim,
                only_new=bool(filter_data.get("onlyNew", True)),
            )

            config = SyncConfig(
                handle=handle,
                github_token=token,
                repo_owner=repo_owner,
                repo_name=repo_name,
                branch=branch,
                destination_dir=dest_dir,
                commit_message=commit_msg,
                is_own_account=is_own,
                cf_api_key=cf_key,
                cf_api_secret=cf_secret,
                sync_filter=sync_filter,
            )

            # Generate job ID and execute sync
            job_id = f"sync_{int(time.time()*1000)}"
            job_state = {
                "id": job_id,
                "status": "RUNNING",
                "handle": handle,
                "repo": f"{repo_owner}/{repo_name}",
                "progressPercent": 0,
                "currentStep": "Initializing sync...",
                "logs": [],
                "result": None,
                "startTime": datetime.now(timezone.utc).isoformat(),
            }

            with SYNC_JOBS_LOCK:
                SYNC_JOBS[job_id] = job_state

            def run_sync_thread():
                def on_progress(msg: str, cur: int, tot: int):
                    with SYNC_JOBS_LOCK:
                        job_state["currentStep"] = msg
                        job_state["progressPercent"] = cur
                        job_state["logs"].append({"time": datetime.now(timezone.utc).isoformat(), "message": msg})

                service = SyncService(
                    codeforces_client=CodeforcesClient(api_key=cf_key, api_secret=cf_secret)
                )
                try:
                    res = service.sync(config, progress_callback=on_progress)
                    with SYNC_JOBS_LOCK:
                        job_state["status"] = "COMPLETED" if not res.errors else ("PARTIAL" if res.successfully_synced > 0 else "FAILED")
                        job_state["progressPercent"] = 100
                        job_state["result"] = res.to_dict()
                        job_state["endTime"] = datetime.now(timezone.utc).isoformat()
                except Exception as ex:
                    with SYNC_JOBS_LOCK:
                        job_state["status"] = "FAILED"
                        job_state["progressPercent"] = 100
                        job_state["error"] = str(ex)
                        job_state["endTime"] = datetime.now(timezone.utc).isoformat()

            # For async responsiveness or synchronous completion
            async_mode = body.get("async", True)
            if async_mode:
                thread = threading.Thread(target=run_sync_thread, daemon=True)
                thread.start()
                self._send_json(202, {
                    "success": True,
                    "jobId": job_id,
                    "status": "RUNNING",
                    "message": "Synchronization started in background."
                })
            else:
                run_sync_thread()
                self._send_json(200, {
                    "success": True,
                    "jobId": job_id,
                    "job": job_state
                })
            return

        self._send_error_json(404, f"API endpoint '{path}' not found")

    def _serve_static(self, path: str):
        if path in ("/", ""):
            file_path = os.path.join(self.web_dir, "index.html")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(self.web_dir, rel_path)

        # Normalize and prevent directory traversal
        real_file = os.path.abspath(file_path)
        real_web = os.path.abspath(self.web_dir)
        if not real_file.startswith(real_web) or not os.path.exists(real_file) or os.path.isdir(real_file):
            # Fallback to index.html for SPA routing
            real_file = os.path.join(real_web, "index.html")

        if not os.path.exists(real_file):
            self.send_error(404, "Static file not found")
            return

        mime_type, _ = mimetypes.guess_type(real_file)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(real_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")


def run_server(host: str = "0.0.0.0", port: int = 8080):
    server_address = (host, port)
    httpd = HTTPServer(server_address, SyncAPIHandler)
    logger.info(f"Codeforces to GitHub Sync Web Server running at http://{host}:{port}")
    print(f"\n=======================================================")
    print(f"  Codeforces -> GitHub Sync Dashboard & API Server")
    print(f"  URL: http://localhost:{port}")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Codeforces to GitHub Sync API Server")
    default_port = int(os.environ.get("PORT", 8080))
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host address")
    parser.add_argument("--port", type=int, default=default_port, help="Port number")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_server(host=args.host, port=args.port)
