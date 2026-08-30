"""
Command Line Interface (CLI) for Codeforces to GitHub Repository Synchronization.
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

from cf_sync.core.models import SyncConfig, SyncFilter, VerdictMode
from cf_sync.services.codeforces_client import CodeforcesClient
from cf_sync.services.sync_service import SyncService


def main():
    parser = argparse.ArgumentParser(
        description="Codeforces Submission -> GitHub Repository Synchronization CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required arguments
    parser.add_argument("--handle", "-u", required=True, help="Codeforces user handle")
    parser.add_argument("--repo", "-r", required=True, help="Target GitHub repository in 'owner/repo' format")
    parser.add_argument(
        "--token",
        "-t",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (can also be passed via GITHUB_TOKEN env var)",
    )

    # Optional repository target arguments
    parser.add_argument("--branch", "-b", default="main", help="Target repository branch")
    parser.add_argument("--dir", "-d", default="codeforces", help="Destination directory inside repository")
    parser.add_argument("--message", "-m", default=None, help="Custom Git commit message")

    # Flow A vs Flow B
    parser.add_argument(
        "--own-account",
        action="store_true",
        help="Sync authenticated user's own handle (includes source code if permitted)",
    )
    parser.add_argument("--cf-api-key", default=os.environ.get("CODEFORCES_API_KEY"), help="Codeforces API Key")
    parser.add_argument("--cf-api-secret", default=os.environ.get("CODEFORCES_API_SECRET"), help="Codeforces API Secret")

    # Filters
    parser.add_argument(
        "--verdict",
        choices=["ALL", "ACCEPTED_ONLY", "REJECTED_ONLY"],
        default="ALL",
        help="Submission verdict filter",
    )
    parser.add_argument("--contest", type=int, default=None, help="Filter by specific contest ID")
    parser.add_argument("--problem", default=None, help="Filter by problem index (e.g. A, B, C)")
    parser.add_argument("--tag", default=None, help="Filter by problem tag (e.g. dp, greedy, math)")
    parser.add_argument("--language", default=None, help="Filter by programming language (e.g. C++, Python)")
    parser.add_argument("--limit", type=int, default=None, help="Max number of submissions to sync")
    parser.add_argument(
        "--all-submissions",
        action="store_true",
        help="Re-sync submissions even if already present in GitHub (disables only_new)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    if not args.token:
        print("Error: GitHub token is required. Pass --token <token> or set GITHUB_TOKEN environment variable.", file=sys.stderr)
        sys.exit(1)

    if "/" not in args.repo:
        print(f"Error: Target repo '{args.repo}' must be in 'owner/repo' format (e.g. 'octocat/my-solutions').", file=sys.stderr)
        sys.exit(1)

    owner, repo_name = args.repo.split("/", 1)

    # Logging setup
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    sync_filter = SyncFilter(
        verdict_mode=VerdictMode(args.verdict),
        contest_id=args.contest,
        problem_index=args.problem,
        problem_tag=args.tag,
        language=args.language,
        limit=args.limit,
        only_new=not args.all_submissions,
    )

    config = SyncConfig(
        handle=args.handle,
        github_token=args.token,
        repo_owner=owner,
        repo_name=repo_name,
        branch=args.branch,
        destination_dir=args.dir,
        commit_message=args.message,
        is_own_account=args.own_account,
        cf_api_key=args.cf_api_key,
        cf_api_secret=args.cf_api_secret,
        sync_filter=sync_filter,
    )

    print(f"\n=======================================================")
    print(f"  Codeforces -> GitHub Sync Engine")
    print(f"  Handle:     {args.handle} (Flow: {'Flow A - Own Account' if args.own_account else 'Flow B - Public Handle'})")
    print(f"  Repository: {owner}/{repo_name} (Branch: {args.branch})")
    print(f"  Target Dir: {args.dir}")
    print(f"=======================================================\n")

    def progress_callback(message: str, current: int, total: int):
        pct = f"[{current}%]" if total else ""
        print(f"--> {pct} {message}")

    cf_client = CodeforcesClient(api_key=args.cf_api_key, api_secret=args.cf_api_secret)
    service = SyncService(codeforces_client=cf_client)

    result = service.sync(config, progress_callback=progress_callback)

    print("\n----------------- Synchronization Summary -----------------")
    print(f"Total Submissions Fetched:  {result.total_fetched}")
    print(f"Eligible Submissions:       {result.eligible_submissions}")
    print(f"Already Synchronized:       {result.already_synced}")
    print(f"Successfully Synced:        {result.successfully_synced}")
    print(f"  - With Source Code:       {result.successfully_synced - result.source_unavailable}")
    print(f"  - Metadata Only (Flow B): {result.source_unavailable}")
    print(f"Failed:                     {result.failed}")

    if result.commit_url:
        print(f"\nCommit URL: {result.commit_url}")

    if result.errors:
        print("\nErrors / Warnings:")
        for err in result.errors:
            print(f"  * {err}")

    if result.failed > 0 or result.errors:
        sys.exit(1 if result.successfully_synced == 0 else 0)


if __name__ == "__main__":
    main()
