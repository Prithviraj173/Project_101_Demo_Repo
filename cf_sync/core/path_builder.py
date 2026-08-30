"""
Path and filename builder with strict sanitization, path traversal prevention,
and Windows/POSIX compatibility.
"""
import re
from typing import Optional
from cf_sync.core.models import Submission
from cf_sync.core.language_mapper import default_language_mapper, LanguageMapper

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


def sanitize_path_segment(name: Optional[str], default: str = "item", max_length: int = 80) -> str:
    r"""
    Sanitizes a single segment of a path (e.g. folder name, file basename):
    - Strips path traversal sequences (.. / \)
    - Replaces forbidden filesystem characters with hyphen
    - Handles Windows reserved device names
    - Strips leading/trailing dots and spaces
    - Limits length while maintaining legibility
    """
    if not name:
        return default

    # Remove null bytes and control chars
    clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", str(name))

    # Replace forbidden path characters: / \ : * ? " < > | [ ] and whitespace
    clean = re.sub(r'[\\/:*?"<>|\r\n\t\[\]]+', "-", clean)

    # Collapse multiple hyphens or spaces into a single hyphen
    clean = re.sub(r"[\s\-]+", "-", clean)

    # Strip leading/trailing dots, hyphens, and spaces
    clean = clean.strip(" .-_")

    if not clean:
        clean = default

    # Check for Windows reserved names
    base_check = clean.split(".")[0].upper()
    if base_check in WINDOWS_RESERVED_NAMES:
        clean = f"_{clean}"

    # Truncate length if needed
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip(" .-_")

    return clean or default


class PathBuilder:
    """
    Constructs deterministic, sanitized repository paths for Codeforces submissions.
    """

    def __init__(self, base_dir: str = "codeforces", language_mapper: Optional[LanguageMapper] = None):
        self.base_dir = self._sanitize_base_dir(base_dir)
        self.language_mapper = language_mapper or default_language_mapper

    @staticmethod
    def _sanitize_base_dir(base_dir: str) -> str:
        if not base_dir:
            return "codeforces"
        segments = [s for s in re.split(r"[\\/]+", base_dir) if s and s != "." and s != ".."]
        clean_segments = [sanitize_path_segment(seg, default="dir") for seg in segments]
        return "/".join(clean_segments) if clean_segments else "codeforces"

    def get_contest_folder(self, contest_id: Optional[int], contest_name: Optional[str] = None) -> str:
        """Generates folder name for contest, e.g. '2048-Example-Round' or 'problemset'"""
        if contest_id is not None:
            cid_str = str(contest_id)
            if contest_name:
                name_clean = sanitize_path_segment(contest_name, default="Contest")
                return f"{cid_str}-{name_clean}"
            return f"{cid_str}-Contest"
        return "problemset"

    def get_problem_folder(self, problem_index: str, problem_name: Optional[str] = None) -> str:
        """Generates folder name for problem, e.g. 'A-Robots'"""
        idx_clean = sanitize_path_segment(problem_index, default="A")
        if problem_name:
            name_clean = sanitize_path_segment(problem_name, default="Problem")
            return f"{idx_clean}-{name_clean}"
        return idx_clean

    def get_solution_filename(self, language: str) -> str:
        """Generates solution filename with appropriate extension, e.g. 'solution.cpp'"""
        ext = self.language_mapper.get_extension(language)
        return f"solution.{ext}"

    def get_rating_folder(self, rating: Optional[int]) -> str:
        """Generates zero-padded 4-digit folder name for rating, e.g. '0800', '1200', '2100' or 'unrated'"""
        if rating is not None and rating > 0:
            return f"{rating:04d}"
        return "unrated"

    def get_tag_folder(self, tag: str) -> str:
        """Generates clean folder name for tag topic, e.g. 'dp', 'math', 'greedy'"""
        return sanitize_path_segment(tag, default="general")

    def build_paths(self, submission: Submission) -> dict:
        """
        Returns primary path dictionary containing:
        - folder_path: Directory path in repo
        - solution_path: Full relative POSIX path for solution file
        - metadata_path: Full relative POSIX path for metadata.json
        """
        contest_folder = self.get_contest_folder(submission.contest_id, submission.contest_name)
        problem_folder = self.get_problem_folder(submission.problem.index, submission.problem.name)
        solution_filename = self.get_solution_filename(submission.programming_language)

        folder_path = f"{self.base_dir}/{contest_folder}/{problem_folder}"
        solution_path = f"{folder_path}/{solution_filename}"
        metadata_path = f"{folder_path}/metadata.json"

        return {
            "folder_path": folder_path,
            "solution_path": solution_path,
            "metadata_path": metadata_path,
        }

    def build_layout_file_destinations(self, submission: Submission, organize_mode: str = "ALL") -> list:
        """
        Returns list of (solution_path, metadata_path) pairs for the chosen organize mode.
        - CONTEST: codeforces/by-contest/<contest-id>-<contest-name>/<problem-index>-<name>/...
        - RATING:  codeforces/by-rating/<rating>/<problem-index>-<name>/...
        - TAG:     codeforces/by-tag/<tag>/<problem-index>-<name>/...
        - ALL:     Creates by-contest, by-rating, and by-tag entries!
        """
        problem_folder = self.get_problem_folder(submission.problem.index, submission.problem.name)
        solution_filename = self.get_solution_filename(submission.programming_language)
        results = []

        # 1. By-contest layout
        if organize_mode in ("ALL", "CONTEST"):
            contest_folder = self.get_contest_folder(submission.contest_id, submission.contest_name)
            folder = f"{self.base_dir}/by-contest/{contest_folder}/{problem_folder}" if organize_mode == "ALL" else f"{self.base_dir}/{contest_folder}/{problem_folder}"
            results.append((f"{folder}/{solution_filename}", f"{folder}/metadata.json"))

        # 2. By-rating layout (sorted by rating!)
        if organize_mode in ("ALL", "RATING"):
            rating_folder = self.get_rating_folder(submission.problem.rating)
            folder = f"{self.base_dir}/by-rating/{rating_folder}/{problem_folder}"
            results.append((f"{folder}/{solution_filename}", f"{folder}/metadata.json"))

        # 3. By-tag layout (organized by problem topic tags!)
        if organize_mode in ("ALL", "TAG"):
            tags = submission.problem.tags or ["general"]
            for tag in tags:
                tag_folder = self.get_tag_folder(tag)
                folder = f"{self.base_dir}/by-tag/{tag_folder}/{problem_folder}"
                results.append((f"{folder}/{solution_filename}", f"{folder}/metadata.json"))

        return results
