"""
Synchronization Orchestrator coordinating Codeforces API retrieval, filtering,
path generation, metadata formatting, and GitHub repository committing.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set

from cf_sync.core.filters import FilterPipeline
from cf_sync.core.metadata import MetadataGenerator
from cf_sync.core.models import (
    Submission,
    SubmissionSyncStatus,
    SyncConfig,
    SyncItemResult,
    SyncResult,
)
from cf_sync.core.path_builder import PathBuilder
from cf_sync.services.codeforces_client import (
    CodeforcesAPIError,
    CodeforcesClient,
    CodeforcesHandleNotFoundError,
)
from cf_sync.services.github_client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubPermissionError,
)

logger = logging.getLogger(__name__)


class SyncService:
    """
    High-level orchestrator for Codeforces to GitHub synchronization.
    """

    def __init__(
        self,
        codeforces_client: Optional[CodeforcesClient] = None,
        metadata_generator: Optional[MetadataGenerator] = None,
    ):
        self.codeforces_client = codeforces_client or CodeforcesClient()
        self.metadata_generator = metadata_generator or MetadataGenerator()

    def sync(
        self,
        config: SyncConfig,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> SyncResult:
        """
        Executes an end-to-end synchronization run based on provided SyncConfig.
        """
        result = SyncResult()

        def report(msg: str, current: int = 0, total: int = 0):
            logger.info(f"Sync [{config.handle} -> {config.repo_owner}/{config.repo_name}]: {msg}")
            if progress_callback:
                progress_callback(msg, current, total)

        report("Starting Codeforces handle verification...", 0, 100)

        # 1. Validate Codeforces handle
        try:
            cf_user = self.codeforces_client.validate_handle(config.handle)
            report(f"Codeforces user '{cf_user.get('handle')}' verified (Rating: {cf_user.get('rating', 'Unrated')})", 10, 100)
        except CodeforcesHandleNotFoundError as e:
            err = f"Codeforces handle '{config.handle}' not found: {str(e)}"
            result.errors.append(err)
            report(err, 0, 100)
            return result
        except Exception as e:
            err = f"Codeforces validation failed: {str(e)}"
            result.errors.append(err)
            report(err, 0, 100)
            return result

        # 2. Verify GitHub access & target repository
        report("Verifying GitHub credentials and repository permissions...", 15, 100)
        try:
            github_client = GitHubClient(token=config.github_token)
            github_client.verify_write_access(config.repo_owner, config.repo_name)
            report(f"GitHub access confirmed for {config.repo_owner}/{config.repo_name}", 25, 100)
        except (GitHubAuthError, GitHubPermissionError, GitHubAPIError) as e:
            err = f"GitHub verification error: {str(e)}"
            result.errors.append(err)
            report(err, 0, 100)
            return result

        # 3. Retrieve already synchronized submission IDs
        report("Inspecting repository for existing synchronized submissions...", 30, 100)
        try:
            synced_ids: Set[int] = github_client.fetch_synced_submission_ids(
                owner=config.repo_owner,
                repo=config.repo_name,
                branch=config.branch,
                base_dir=config.destination_dir,
            )
            result.already_synced = len(synced_ids)
            report(f"Found {len(synced_ids)} previously synchronized submissions in repository index", 35, 100)
        except Exception as e:
            logger.warning(f"Could not retrieve existing sync index: {e}")
            synced_ids = set()

        # 4. Fetch Codeforces submissions
        report("Fetching submissions from Codeforces API...", 40, 100)
        try:
            # Preload contest names
            self.codeforces_client.load_contest_names()

            max_fetch = config.sync_filter.limit if config.sync_filter.limit and config.sync_filter.limit > 0 else None
            submissions = self.codeforces_client.fetch_all_submissions(
                handle=config.handle,
                max_submissions=max_fetch,
                is_own_account=config.is_own_account,
            )
            result.total_fetched = len(submissions)
            report(f"Fetched {len(submissions)} submissions from Codeforces", 55, 100)
        except CodeforcesAPIError as e:
            err = f"Failed to fetch submissions from Codeforces: {str(e)}"
            result.errors.append(err)
            report(err, 0, 100)
            return result

        # 5. Apply filters
        report("Filtering submissions against configured criteria...", 60, 100)
        pipeline = FilterPipeline.from_sync_filter(config.sync_filter, synced_ids=synced_ids)
        eligible_submissions = pipeline.apply(submissions)
        result.eligible_submissions = len(eligible_submissions)

        report(f"Found {len(eligible_submissions)} eligible submissions ready for synchronization", 65, 100)

        if not eligible_submissions:
            report("No new eligible submissions to synchronize. Sync complete.", 100, 100)
            return result

        # 6. Build files to commit and track item statuses
        report("Generating repository paths, source files, and metadata...", 70, 100)
        path_builder = PathBuilder(base_dir=config.destination_dir)
        files_to_commit: Dict[str, str] = {}
        newly_synced_ids: Set[int] = set()

        for idx, sub in enumerate(eligible_submissions, start=1):
            paths = path_builder.build_paths(sub)
            folder_path = paths["folder_path"]
            sol_path = paths["solution_path"]
            meta_path = paths["metadata_path"]

            sub.target_path = sol_path

            # Generate contents
            try:
                meta_content = self.metadata_generator.generate_metadata_json(sub, handle=config.handle)
                sol_content = self.metadata_generator.format_solution_file_content(sub, handle=config.handle)

                files_to_commit[meta_path] = meta_content
                files_to_commit[sol_path] = sol_content

                newly_synced_ids.add(sub.id)

                if sub.source_available:
                    status = SubmissionSyncStatus.SYNCED
                    msg = "Synced with source code"
                    result.successfully_synced += 1
                else:
                    status = SubmissionSyncStatus.SOURCE_UNAVAILABLE
                    msg = "Synced metadata (source unavailable via public API)"
                    result.source_unavailable += 1
                    result.successfully_synced += 1

                result.items.append(
                    SyncItemResult(
                        submission_id=sub.id,
                        contest_id=sub.contest_id,
                        problem_index=sub.problem.index,
                        problem_name=sub.problem.name,
                        verdict=sub.verdict,
                        language=sub.programming_language,
                        status=status,
                        file_path=sol_path,
                        message=msg,
                        source_available=sub.source_available,
                    )
                )
            except Exception as e:
                err = f"Failed to generate files for submission {sub.id}: {str(e)}"
                result.failed += 1
                result.errors.append(err)
                result.items.append(
                    SyncItemResult(
                        submission_id=sub.id,
                        contest_id=sub.contest_id,
                        problem_index=sub.problem.index,
                        problem_name=sub.problem.name,
                        verdict=sub.verdict,
                        language=sub.programming_language,
                        status=SubmissionSyncStatus.FAILED,
                        file_path=sol_path,
                        message=err,
                        source_available=False,
                    )
                )

        # 7. Update .cf_sync_index.json
        all_synced_ids_list = sorted(list(synced_ids.union(newly_synced_ids)))
        index_payload = {
            "version": "1.0",
            "lastSyncedUtc": datetime.now(timezone.utc).isoformat(),
            "handle": config.handle,
            "totalSyncedCount": len(all_synced_ids_list),
            "syncedSubmissionIds": all_synced_ids_list,
        }
        index_path = f"{config.destination_dir}/.cf_sync_index.json"
        files_to_commit[index_path] = json.dumps(index_payload, indent=2)

        # 8. Commit bundle to GitHub
        report(f"Pushing {len(files_to_commit)} files in single atomic commit to GitHub...", 85, 100)
        try:
            commit_msg = (
                config.commit_message
                or f"Sync {len(eligible_submissions)} Codeforces submissions for {config.handle}"
            )
            commit_sha, commit_url = github_client.commit_files_bundle(
                owner=config.repo_owner,
                repo=config.repo_name,
                branch=config.branch,
                files_to_commit=files_to_commit,
                commit_message=commit_msg,
            )
            result.commit_sha = commit_sha
            result.commit_url = commit_url
            report(f"Successfully committed and pushed to branch '{config.branch}' ({commit_sha[:7]})", 100, 100)
        except Exception as e:
            err = f"GitHub commit push failed: {str(e)}"
            result.errors.append(err)
            # Mark items as failed
            for item in result.items:
                if item.status in (SubmissionSyncStatus.SYNCED, SubmissionSyncStatus.SOURCE_UNAVAILABLE):
                    item.status = SubmissionSyncStatus.FAILED
                    item.message = f"Push failed: {str(e)}"
            result.failed += result.successfully_synced
            result.successfully_synced = 0
            report(err, 100, 100)

        return result
