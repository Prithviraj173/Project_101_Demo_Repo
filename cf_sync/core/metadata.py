"""
Structured metadata generation for synchronized Codeforces submissions.
"""
import json
from typing import Any, Dict, Optional
from cf_sync.core.models import Submission
from cf_sync.core.language_mapper import default_language_mapper, LanguageMapper


class MetadataGenerator:
    """
    Generates metadata.json and solution file comment headers.
    """

    def __init__(self, language_mapper: Optional[LanguageMapper] = None):
        self.language_mapper = language_mapper or default_language_mapper

    def generate_metadata_dict(self, submission: Submission, handle: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a dictionary of preserved submission metadata.
        Does not fabricate any unavailable values.
        """
        meta: Dict[str, Any] = {
            "submissionId": submission.id,
            "handle": handle or (submission.author_members[0] if submission.author_members else None),
            "contestId": submission.contest_id,
            "contestName": submission.contest_name,
            "problem": {
                "index": submission.problem.index,
                "name": submission.problem.name,
                "rating": submission.problem.rating,
                "tags": submission.problem.tags,
                "type": submission.problem.problem_type,
                "points": submission.problem.points,
            },
            "programmingLanguage": submission.programming_language,
            "verdict": submission.verdict,
            "passedTestCount": submission.pass_test_count,
            "timeConsumedMillis": submission.time_consumed_millis,
            "memoryConsumedBytes": submission.memory_consumed_bytes,
            "submissionTimeUtc": submission.created_at_utc.isoformat(),
            "problemUrl": submission.problem_url,
            "submissionUrl": submission.submission_url,
            "sourceCodeAvailable": submission.source_available,
        }
        return meta

    def generate_metadata_json(self, submission: Submission, handle: Optional[str] = None, indent: int = 2) -> str:
        """Generates formatted metadata.json content."""
        data = self.generate_metadata_dict(submission, handle)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    def generate_solution_header(self, submission: Submission, handle: Optional[str] = None) -> str:
        """
        Generates a clean comment header describing the problem and submission.
        """
        prefix = self.language_mapper.get_comment_prefix(submission.programming_language)
        handle_display = handle or (submission.author_members[0] if submission.author_members else "Codeforces User")
        contest_display = f"{submission.contest_id} - {submission.contest_name}" if submission.contest_name else f"Contest {submission.contest_id}"

        lines = [
            f"Problem: {submission.problem.index}. {submission.problem.name}",
            f"Contest: {contest_display}",
            f"URL: {submission.problem_url}",
            f"Handle: {handle_display}",
            f"Submission ID: {submission.id}",
            f"Language: {submission.programming_language}",
            f"Verdict: {submission.verdict or 'N/A'}",
            f"Date: {submission.created_at_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]

        if submission.problem.rating:
            lines.append(f"Difficulty: {submission.problem.rating}")

        header_lines = [f"{prefix} ==========================================================="]
        for line in lines:
            header_lines.append(f"{prefix} {line}")
        header_lines.append(f"{prefix} ===========================================================")
        header_lines.append("")

        return "\n".join(header_lines)

    def format_solution_file_content(self, submission: Submission, handle: Optional[str] = None) -> str:
        """
        Formats complete solution source file with descriptive header.
        If source code is unavailable (Flow B), includes a clear disclaimer header.
        """
        header = self.generate_solution_header(submission, handle)
        if submission.source_code:
            return f"{header}\n{submission.source_code.strip()}\n"
        else:
            prefix = self.language_mapper.get_comment_prefix(submission.programming_language)
            unavailable_notice = (
                f"{prefix} SOURCE CODE UNAVAILABLE VIA CODEFORCES PUBLIC API\n"
                f"{prefix} Note: Codeforces API only returns source code for the authenticated user's own handle.\n"
                f"{prefix} For full submission details, visit: {submission.submission_url}\n"
            )
            return f"{header}\n{unavailable_notice}\n"
