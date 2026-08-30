// Content Script for Codeforces pages
(function() {
  console.log("[CF-GitHub-Sync] Content script loaded on Codeforces.");

  // Check if current page is a submission page
  function isSubmissionPage() {
    return window.location.href.includes("/submission/") || document.querySelector("#program-source-text") !== null;
  }

  function extractSubmissionData() {
    const codeElem = document.querySelector("#program-source-text") || document.querySelector("pre.program-source") || document.querySelector("pre");
    if (!codeElem) return null;

    const sourceCode = codeElem.innerText;

    // Parse problem name and index from page
    let problemIndex = "A";
    let problemName = "Problem";
    let contestId = 0;
    let contestName = "";
    let verdict = "OK";
    let language = "GNU C++20";
    let rating = null;
    let tags = [];

    // Extract table details if present
    const tableRows = document.querySelectorAll(".datatable table tr, .status-frame-datatable tr");
    if (tableRows && tableRows.length > 1) {
      const cells = tableRows[1].querySelectorAll("td");
      if (cells.length >= 4) {
        language = cells[3]?.innerText?.trim() || language;
        verdict = cells[4]?.innerText?.trim() || verdict;
      }
    }

    // Extract problem title link
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
      if (hrefMatch) {
        contestId = parseInt(hrefMatch[1]);
      }
    }

    // Extract contest title
    const contestHeader = document.querySelector("#sidebar a[href*='/contest/']") || document.querySelector(".rtable a");
    if (contestHeader) {
      contestName = contestHeader.innerText.trim();
    }

    const subIdMatch = window.location.href.match(/\/submission\/(\d+)/);
    const submissionId = subIdMatch ? parseInt(subIdMatch[1]) : Date.now();

    return {
      submissionId,
      contestId,
      contestName,
      problemIndex,
      problemName,
      language,
      verdict,
      rating,
      tags,
      problemUrl: problemLink ? problemLink.href : window.location.href,
      submissionUrl: window.location.href,
      sourceCode
    };
  }

  function injectSyncButton() {
    if (!isSubmissionPage()) return;
    if (document.querySelector("#cf-github-sync-btn")) return;

    const targetHeader = document.querySelector(".roundbox.sidebox") || document.querySelector("#pageContent") || document.body;
    
    const syncContainer = document.createElement("div");
    syncContainer.id = "cf-github-sync-container";
    syncContainer.innerHTML = `
      <div class="cf-sync-widget">
        <button id="cf-github-sync-btn" class="cf-sync-button">
          <span class="cf-sync-icon">⚡</span>
          <span id="cf-sync-btn-text">Sync to GitHub</span>
        </button>
        <span id="cf-sync-status" class="cf-sync-status-msg"></span>
      </div>
    `;

    const codeBox = document.querySelector("#program-source-text")?.parentElement || targetHeader.firstChild;
    if (codeBox) {
      codeBox.parentNode.insertBefore(syncContainer, codeBox);
    } else {
      document.body.appendChild(syncContainer);
    }

    document.getElementById("cf-github-sync-btn").addEventListener("click", async () => {
      const btn = document.getElementById("cf-github-sync-btn");
      const btnText = document.getElementById("cf-sync-btn-text");
      const statusMsg = document.getElementById("cf-sync-status");

      btn.disabled = true;
      btnText.innerText = "Syncing...";
      statusMsg.innerText = "Extracting code...";

      // Get settings from storage
      const storage = await chrome.storage.local.get(["ghToken", "ghRepo", "ghBranch", "ghDir", "organizeMode"]);
      if (!storage.ghToken || !storage.ghRepo) {
        statusMsg.innerHTML = `<span style="color:#ef4444;">Please configure your GitHub Token & Repo in the extension popup!</span>`;
        btn.disabled = false;
        btnText.innerText = "Sync to GitHub";
        return;
      }

      const subData = extractSubmissionData();
      if (!subData || !subData.sourceCode) {
        statusMsg.innerHTML = `<span style="color:#ef4444;">Could not extract source code from this page.</span>`;
        btn.disabled = false;
        btnText.innerText = "Sync to GitHub";
        return;
      }

      statusMsg.innerText = "Pushing commit to GitHub...";

      chrome.runtime.sendMessage({
        action: "SYNC_SUBMISSION",
        payload: {
          token: storage.ghToken,
          repo: storage.ghRepo,
          branch: storage.ghBranch || "main",
          baseDir: storage.ghDir || "codeforces",
          organizeMode: storage.organizeMode || "ALL",
          submission: subData
        }
      }, (response) => {
        btn.disabled = false;
        if (response && response.success) {
          btnText.innerText = "✅ Synced!";
          btn.style.background = "linear-gradient(135deg, #10b981, #059669)";
          statusMsg.innerHTML = `<a href="${response.commitUrl}" target="_blank" style="color:#10b981; font-weight:600; text-decoration:underline;">Commit Created on GitHub (${response.commitSha.slice(0, 7)})</a>`;
        } else {
          btnText.innerText = "Sync to GitHub";
          statusMsg.innerHTML = `<span style="color:#ef4444;">Error: ${response ? response.error : 'Unknown error'}</span>`;
        }
      });
    });
  }

  // Inject when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectSyncButton);
  } else {
    injectSyncButton();
  }
})();
