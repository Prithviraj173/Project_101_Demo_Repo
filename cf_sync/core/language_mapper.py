"""
Centralized and extensible mapping from Codeforces language names to file extensions and comment styles.
"""
import re
from typing import Dict, Optional, Tuple


class LanguageDefinition:
    def __init__(self, extension: str, comment_prefix: str = "//", display_name: Optional[str] = None):
        self.extension = extension.lstrip(".")
        self.comment_prefix = comment_prefix
        self.display_name = display_name or extension.upper()


# Centralized dictionary of known Codeforces programming languages
DEFAULT_LANGUAGE_MAP: Dict[str, LanguageDefinition] = {
    # C / C++
    "c": LanguageDefinition("c", "//", "C"),
    "gnu c": LanguageDefinition("c", "//", "C"),
    "gnu c11": LanguageDefinition("c", "//", "C11"),
    "c++": LanguageDefinition("cpp", "//", "C++"),
    "gnu c++": LanguageDefinition("cpp", "//", "C++"),
    "gnu c++11": LanguageDefinition("cpp", "//", "C++11"),
    "gnu c++14": LanguageDefinition("cpp", "//", "C++14"),
    "gnu c++17": LanguageDefinition("cpp", "//", "C++17"),
    "gnu c++20": LanguageDefinition("cpp", "//", "C++20"),
    "gnu c++23": LanguageDefinition("cpp", "//", "C++23"),
    "clang++": LanguageDefinition("cpp", "//", "Clang C++"),
    "clang++17 diagnostics": LanguageDefinition("cpp", "//", "Clang C++17"),
    "clang++20 diagnostics": LanguageDefinition("cpp", "//", "Clang C++20"),
    "ms c++": LanguageDefinition("cpp", "//", "MS C++"),
    "ms c++ 2017": LanguageDefinition("cpp", "//", "MS C++ 2017"),

    # Python / PyPy
    "python": LanguageDefinition("py", "#", "Python"),
    "python 2": LanguageDefinition("py", "#", "Python 2"),
    "python 3": LanguageDefinition("py", "#", "Python 3"),
    "pypy": LanguageDefinition("py", "#", "PyPy"),
    "pypy 2": LanguageDefinition("py", "#", "PyPy 2"),
    "pypy 3": LanguageDefinition("py", "#", "PyPy 3"),
    "pypy 3-64": LanguageDefinition("py", "#", "PyPy 3-64"),

    # Java / Kotlin / Scala
    "java": LanguageDefinition("java", "//", "Java"),
    "java 8": LanguageDefinition("java", "//", "Java 8"),
    "java 11": LanguageDefinition("java", "//", "Java 11"),
    "java 17": LanguageDefinition("java", "//", "Java 17"),
    "java 21": LanguageDefinition("java", "//", "Java 21"),
    "kotlin": LanguageDefinition("kt", "//", "Kotlin"),
    "kotlin 1.5": LanguageDefinition("kt", "//", "Kotlin 1.5"),
    "kotlin 1.6": LanguageDefinition("kt", "//", "Kotlin 1.6"),
    "kotlin 1.7": LanguageDefinition("kt", "//", "Kotlin 1.7"),
    "kotlin 1.8": LanguageDefinition("kt", "//", "Kotlin 1.8"),
    "kotlin 1.9": LanguageDefinition("kt", "//", "Kotlin 1.9"),
    "scala": LanguageDefinition("scala", "//", "Scala"),

    # C# / F#
    "c#": LanguageDefinition("cs", "//", "C#"),
    ".net core c#": LanguageDefinition("cs", "//", "C# .NET"),
    "mono c#": LanguageDefinition("cs", "//", "Mono C#"),
    "f#": LanguageDefinition("fs", "//", "F#"),

    # Rust / Go / D
    "rust": LanguageDefinition("rs", "//", "Rust"),
    "rust 2021": LanguageDefinition("rs", "//", "Rust 2021"),
    "go": LanguageDefinition("go", "//", "Go"),
    "d": LanguageDefinition("d", "//", "D"),
    "d dmd": LanguageDefinition("d", "//", "D"),

    # JavaScript / TypeScript / Node
    "javascript": LanguageDefinition("js", "//", "JavaScript"),
    "node.js": LanguageDefinition("js", "//", "Node.js"),
    "typescript": LanguageDefinition("ts", "//", "TypeScript"),

    # Ruby / PHP / Perl
    "ruby": LanguageDefinition("rb", "#", "Ruby"),
    "ruby 3": LanguageDefinition("rb", "#", "Ruby 3"),
    "php": LanguageDefinition("php", "//", "PHP"),
    "php 8": LanguageDefinition("php", "//", "PHP 8"),
    "perl": LanguageDefinition("pl", "#", "Perl"),

    # Haskell / OCaml
    "haskell": LanguageDefinition("hs", "--", "Haskell"),
    "ghc haskell": LanguageDefinition("hs", "--", "Haskell"),
    "ocaml": LanguageDefinition("ml", "(*", "OCaml"),

    # Swift / Pascal / Ada / others
    "swift": LanguageDefinition("swift", "//", "Swift"),
    "pascal": LanguageDefinition("pas", "//", "Pascal"),
    "fpc": LanguageDefinition("pas", "//", "Free Pascal"),
    "delphi": LanguageDefinition("pas", "//", "Delphi"),
    "ada": LanguageDefinition("adb", "--", "Ada"),
    "r": LanguageDefinition("r", "#", "R"),
    "lua": LanguageDefinition("lua", "--", "Lua"),
}


class LanguageMapper:
    """
    Extensible language mapper translating Codeforces language names
    to standard file extensions and comment styles with deterministic fallbacks.
    """

    def __init__(self, custom_mappings: Optional[Dict[str, LanguageDefinition]] = None):
        self._map = dict(DEFAULT_LANGUAGE_MAP)
        if custom_mappings:
            for k, v in custom_mappings.items():
                self.register_language(k, v.extension, v.comment_prefix, v.display_name)

    @staticmethod
    def _normalize_key(name: str) -> str:
        if not name:
            return ""
        norm = name.strip().lower()
        norm = re.sub(r"\s+", " ", norm)
        return norm

    def register_language(
        self,
        language_name: str,
        extension: str,
        comment_prefix: str = "//",
        display_name: Optional[str] = None
    ) -> None:
        """Register a new language or override an existing mapping."""
        key = self._normalize_key(language_name)
        self._map[key] = LanguageDefinition(extension, comment_prefix, display_name)

    def resolve(self, language_name: str) -> Tuple[str, str]:
        """
        Resolves language name to (file_extension, comment_prefix).
        If not explicitly mapped, uses heuristic matching and deterministic fallback.
        """
        if not language_name:
            return "txt", "//"

        key = self._normalize_key(language_name)

        # 1. Exact match in registry
        if key in self._map:
            defn = self._map[key]
            return defn.extension, defn.comment_prefix

        # 2. Substring / regex heuristic matching (ordering matters: e.g. javascript before java)
        if "c++" in key or "g++" in key or "clang++" in key:
            return "cpp", "//"
        if "python" in key or "pypy" in key:
            return "py", "#"
        if "javascript" in key or "node" in key:
            return "js", "//"
        if "typescript" in key:
            return "ts", "//"
        if "java" in key:
            return "java", "//"
        if "kotlin" in key:
            return "kt", "//"
        if "rust" in key:
            return "rs", "//"
        if "golang" in key or key.startswith("go ") or key == "go":
            return "go", "//"
        if "c#" in key or "csharp" in key:
            return "cs", "//"
        if "ruby" in key:
            return "rb", "#"
        if "haskell" in key:
            return "hs", "--"
        if "pascal" in key or "delphi" in key:
            return "pas", "//"
        if "scala" in key:
            return "scala", "//"
        if "swift" in key:
            return "swift", "//"
        if "php" in key:
            return "php", "//"
        if "perl" in key:
            return "pl", "#"
        if key.startswith("c ") or key == "c" or "gcc" in key:
            return "c", "//"

        # 3. Deterministic safe fallback: sanitize key into short token or default to "txt"
        fallback_token = re.sub(r"[^a-z0-9]", "", key)
        if 2 <= len(fallback_token) <= 4:
            return fallback_token, "//"

        return "txt", "//"

    def get_extension(self, language_name: str) -> str:
        return self.resolve(language_name)[0]

    def get_comment_prefix(self, language_name: str) -> str:
        return self.resolve(language_name)[1]


default_language_mapper = LanguageMapper()
