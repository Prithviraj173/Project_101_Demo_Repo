# Project-101: Codeforces → GitHub Repository Sync Engine

A production-grade, secure, and idempotent synchronization engine that backs up and organizes Codeforces submissions into any GitHub repository.

---

## Key Features

- **Automated & Idempotent Synchronization**: Keeps your GitHub repository in sync without creating redundant commits or duplicate files on repeated runs using `.cf_sync_index.json` state tracking.
- **Codeforces Official API Compliance**:
  - **Flow A (Own Account)**: Imports accepted/rejected solutions with full source code where authorized by Codeforces.
  - **Flow B (Public Handles)**: Imports structured metadata without scraping or violating platform API policies.
- **Atomic Single-Commit GitHub Engine**: Uses the GitHub Git Data API (`/git/blobs` -> `/git/trees` -> `/git/commits` -> `/git/refs`) to bundle multiple files into one clean atomic commit rather than dozens of separate commits.
- **Strict Security & Path Sanitization**: Completely prevents directory traversal (`../`, absolute paths, forbidden characters, and Windows reserved device names like `CON`, `PRN`, `AUX`, `NUL`).
- **Extensible Language Mapping**: Centralized mapping covering 40+ programming languages (C++, Python, Java, Kotlin, Rust, Go, TypeScript, Haskell, etc.) with deterministic safe fallbacks.
- **Multi-Interface Architecture**:
  - 🖥️ **Interactive Web Dashboard**: Beautiful UI with dark/light themes, live problem search, and real-time terminal logs.
  - ⚙️ **Command Line Interface (CLI)**: Terminal tool for automated scripting and CI/CD pipelines.
  - 🔌 **REST API & Python SDK**: Clean service layer ready for browser extensions and cron jobs.

---

## Repository Structure

```
Project-101/
├── cf_sync/
│   ├── core/
│   │   ├── models.py           # Domain models and dataclasses
│   │   ├── language_mapper.py  # Extensible language -> extension mapper
│   │   ├── path_builder.py     # Filesystem-safe, traversal-proof path generator
│   │   ├── filters.py          # Composable filter pipeline
│   │   └── metadata.py         # Formatted metadata & solution header builder
│   ├── services/
│   │   ├── codeforces_client.py# Rate-limited Codeforces API client with retries
│   │   ├── github_client.py    # GitHub client with atomic tree committing
│   │   └── sync_service.py     # High-level synchronization orchestrator
│   ├── api/
│   │   └── server.py           # REST API server & static web server
│   ├── web/
│   │   ├── index.html          # Web dashboard interface
│   │   ├── style.css           # Modern stylesheet (dark/light themes)
│   │   └── app.js              # Frontend application logic
│   └── cli.py                  # Command Line Interface
├── tests/                      # Automated test suite (100% mocked)
│   ├── test_language_mapper.py
│   ├── test_path_builder.py
│   ├── test_filters.py
│   ├── test_metadata.py
│   ├── test_codeforces_client.py
│   ├── test_github_client.py
│   ├── test_sync_service.py
│   ├── test_api.py
│   └── test_security.py
└── README.md
```

---

## Getting Started

### 1. Launch the Web Dashboard
```bash
python -m cf_sync.api.server --port 8080
```
Open [http://localhost:8080](http://localhost:8080) in your browser:
1. Enter your Codeforces handle and click **Verify**.
2. Enter your GitHub Personal Access Token (PAT) and select your destination repository.
3. Configure your desired submission filters (Accepted only, Contest ID, Date range, etc.).
4. Click **Start Synchronization** to execute the sync with live progress tracking!

### 2. Run via Command Line (CLI)
```bash
python -m cf_sync.cli \
  --handle "tourist" \
  --repo "RishabhRaj120/Project-101" \
  --token "ghp_your_github_token" \
  --branch "prithvi" \
  --dir "codeforces" \
  --verdict "ACCEPTED_ONLY" \
  --limit 50
```

### 3. Run Automated Tests
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## GitHub Repository Output Structure

Synchronized submissions are structured predictably as follows:

```
codeforces/
├── 2048-Educational-Codeforces-Round-170/
│   ├── A-Two-Screens/
│   │   ├── solution.cpp
│   │   └── metadata.json
│   └── B-Binomial-Coefficients/
│       ├── solution.py
│       └── metadata.json
└── .cf_sync_index.json
```

---

## License & Credits

Developed for Project 101.
