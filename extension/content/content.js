// Content Script for Codeforces pages
(function() {
  console.log("[CF-GitHub-Sync] Content script active on Codeforces.");

  // 1. Inject Top Bar Button on Submissions Table Page
  function injectTableSyncBar() {
    const tableHeader = document.querySelector(".datatable, .status-frame-datatable");
    if (!tableHeader || document.querySelector("#cf-table-sync-bar")) return;

    // Detect user handle robustly (from storage, URL, or page DOM)
    chrome.storage.local.get(["cfHandle", "ghToken", "ghRepo", "organizeMode"]).then(storage => {
      let handle = storage.cfHandle || "";

      if (!handle || handle.toLowerCase() === "personal" || handle.toLowerCase() === "user") {
        const pathParts = window.location.pathname.split("/").filter(Boolean);
        if (pathParts[0] === "submissions" && pathParts[1]) {
          handle = pathParts[1];
        }
      }

      if (!handle || handle.toLowerCase() === "personal" || handle.toLowerCase() === "user") {
        const profileEl = document.querySelector("#sidebar a[href*='/profile/']") || document.querySelector("a[href*='/profile/']");
        if (profileEl) handle = profileEl.innerText.trim();
      }

      handle = handle || "Sinister007";

      const bar = document.createElement("div");
      bar.id = "cf-table-sync-bar";
      bar.className = "cf-sync-table-bar";
      bar.innerHTML = `
        <div class="cf-table-bar-inner">
          <div class="cf-bar-title">
            <span class="cf-logo-badge">⚡ CF Sync</span>
            <span>Sync all accepted solutions for <strong>@${handle}</strong> into your GitHub repository</span>
          </div>
          <button id="cf-quick-sync-all-btn" class="cf-sync-button">
            <span>🚀 Sync All Accepted (Day 1 Onwards)</span>
          </button>
        </div>
        <div id="cf-table-sync-status" class="cf-table-sync-status hidden"></div>
      `;

      tableHeader.parentNode.insertBefore(bar, tableHeader);

      document.getElementById("cf-quick-sync-all-btn").addEventListener("click", async () => {
        const btn = document.getElementById("cf-quick-sync-all-btn");
        const statusDiv = document.getElementById("cf-table-sync-status");

        btn.disabled = true;
        btn.innerText = "⏳ Syncing into GitHub...";
        statusDiv.className = "cf-table-sync-status info";
        statusDiv.innerHTML = "Fetching all Accepted solutions from Day 1 and committing...";
        statusDiv.classList.remove("hidden");

        const curStorage = await chrome.storage.local.get(["cfHandle", "ghToken", "ghRepo", "organizeMode"]);
        if (!curStorage.ghToken) {
          statusDiv.className = "cf-table-sync-status error";
          statusDiv.innerHTML = `⚠️ Please click the <strong>⚡ extension icon</strong> in your Chrome toolbar to enter your GitHub token first!`;
          btn.disabled = false;
          btn.innerText = "🚀 Sync All Accepted (Day 1 Onwards)";
          return;
        }

        const effectiveHandle = curStorage.cfHandle || handle;
        const targetRepo = curStorage.ghRepo || "CF-Submissions-all-time";

        chrome.runtime.sendMessage({
          action: "SYNC_ALL_FROM_DAY_ONE",
          payload: {
            token: curStorage.ghToken,
            handle: effectiveHandle,
            repoName: targetRepo,
            organizeMode: curStorage.organizeMode || "ALL"
          }
        }, (res) => {
          btn.disabled = false;
          btn.innerText = "🚀 Sync All Accepted (Day 1 Onwards)";

          if (res && res.success) {
            statusDiv.className = "cf-table-sync-status success";
            statusDiv.innerHTML = `✅ <strong>Success!</strong> Pushed ${res.count} Accepted problems into GitHub repository.<br/><a href="${res.repoUrl}" target="_blank" style="color:#059669; font-weight:bold; text-decoration:underline;">View Your Repository on GitHub ↗</a>`;
          } else {
            statusDiv.className = "cf-table-sync-status error";
            statusDiv.innerHTML = `❌ Sync error: ${res ? res.error : 'Unknown error'}`;
          }
        });
      });
    });
  }

  // 2. Inject Button on Submission Details / Source Code Modal
  function injectSubmissionModalSyncButton() {
    const codeElem = document.querySelector("#program-source-text") || document.querySelector("pre.program-source");
    if (!codeElem || document.querySelector("#cf-github-sync-container")) return;

    const sourceCode = codeElem.innerText;

    // Parse problem info from page or modal
    let problemIndex = "A";
    let problemName = "Problem";
    let contestId = 0;
    let contestName = "";
    let verdict = "OK";
    let language = "GNU C++20";

    const problemLink = document.querySelector("a[href*='/problem/']");
    if (problemLink) {
      const pText = problemLink.innerText.trim();
      const match = pText.match(/^([A-Z0-9]+)\s*-\s*(.+)$/i);
      if (match) {
        problemIndex = match[1];
        problemName = match[2];
      } else {
        problemName = pText;
      }
      const hrefMatch = problemLink.getAttribute("href").match(/\/contest\/(\d+)/);
      if (hrefMatch) contestId = parseInt(hrefMatch[1]);
    }

    const subIdMatch = window.location.href.match(/\/submission\/(\d+)/);
    const submissionId = subIdMatch ? parseInt(subIdMatch[1]) : Date.now();

    const syncContainer = document.createElement("div");
    syncContainer.id = "cf-github-sync-container";
    syncContainer.innerHTML = `
      <div class="cf-sync-widget">
        <button id="cf-github-sync-btn" class="cf-sync-button">
          <span>⚡ Sync to GitHub</span>
        </button>
        <span id="cf-sync-status" class="cf-sync-status-msg"></span>
      </div>
    `;

    codeElem.parentNode.insertBefore(syncContainer, codeElem);

    document.getElementById("cf-github-sync-btn").addEventListener("click", async () => {
      const btn = document.getElementById("cf-github-sync-btn");
      const statusMsg = document.getElementById("cf-sync-status");

      btn.disabled = true;
      btn.innerText = "Syncing...";
      statusMsg.innerText = "Pushing to GitHub...";

      const storage = await chrome.storage.local.get(["ghToken", "ghRepo", "ghBranch", "ghDir", "organizeMode"]);
      if (!storage.ghToken) {
        statusMsg.innerHTML = `<span style="color:#ef4444;">Please set GitHub Token in extension popup!</span>`;
        btn.disabled = false;
        btn.innerText = "⚡ Sync to GitHub";
        return;
      }

      chrome.runtime.sendMessage({
        action: "SYNC_SUBMISSION",
        payload: {
          token: storage.ghToken,
          repo: storage.ghRepo || "Codeforces-Solutions",
          branch: storage.ghBranch || "main",
          baseDir: storage.ghDir || "codeforces",
          organizeMode: storage.organizeMode || "ALL",
          submission: {
            submissionId,
            contestId,
            contestName,
            problemIndex,
            problemName,
            language,
            verdict,
            sourceCode,
            submissionUrl: window.location.href,
            problemUrl: problemLink ? problemLink.href : window.location.href,
          }
        }
      }, (res) => {
        btn.disabled = false;
        if (res && res.success) {
          btn.innerText = "✅ Synced!";
          btn.style.background = "linear-gradient(135deg, #10b981, #059669)";
          statusMsg.innerHTML = `<a href="${res.commitUrl}" target="_blank" style="color:#10b981; font-weight:bold; text-decoration:underline;">Commit Created ↗</a>`;
        } else {
          btn.innerText = "⚡ Sync to GitHub";
          statusMsg.innerHTML = `<span style="color:#ef4444;">Error: ${res ? res.error : 'Failed'}</span>`;
        }
      });
    });
  }

  function init() {
    injectTableSyncBar();
    injectSubmissionModalSyncButton();
  }

  // Observer for dynamic Codeforces AJAX modals
  const observer = new MutationObserver(() => {
    init();
  });

  observer.observe(document.body, { childList: true, subtree: true });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
