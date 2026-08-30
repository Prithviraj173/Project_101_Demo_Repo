document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const cfHandleInput = document.getElementById("cfHandle");
  const cfVerifyBtn = document.getElementById("cfVerifyBtn");
  const cfProfileBanner = document.getElementById("cfProfileBanner");
  const cfAvatar = document.getElementById("cfAvatar");
  const cfProfileHandle = document.getElementById("cfProfileHandle");
  const cfRankBadge = document.getElementById("cfRankBadge");
  const cfRatingBadge = document.getElementById("cfRatingBadge");
  const flowNotice = document.getElementById("flowNotice");
  const flowRadios = document.querySelectorAll('input[name="flowMode"]');

  const ghTokenInput = document.getElementById("ghToken");
  const ghConnectBtn = document.getElementById("ghConnectBtn");
  const ghUserBanner = document.getElementById("ghUserBanner");
  const ghAvatar = document.getElementById("ghAvatar");
  const ghUsername = document.getElementById("ghUsername");
  const ghRepoSelect = document.getElementById("ghRepoSelect");
  const ghBranchSelect = document.getElementById("ghBranchSelect");
  const ghDestDir = document.getElementById("ghDestDir");

  const filterVerdict = document.getElementById("filterVerdict");
  const filterLimit = document.getElementById("filterLimit");
  const filterContest = document.getElementById("filterContest");
  const filterProblemIndex = document.getElementById("filterProblemIndex");
  const filterLanguage = document.getElementById("filterLanguage");
  const filterTag = document.getElementById("filterTag");
  const filterOnlyNew = document.getElementById("filterOnlyNew");

  const previewBtn = document.getElementById("previewBtn");
  const syncNowBtn = document.getElementById("syncNowBtn");
  const syncBtnSpinner = document.getElementById("syncBtnSpinner");

  const progressCard = document.getElementById("progressCard");
  const progressBar = document.getElementById("progressBar");
  const progressPercentText = document.getElementById("progressPercentText");
  const currentStepText = document.getElementById("currentStepText");
  const syncStatusBadge = document.getElementById("syncStatusBadge");
  const terminalBody = document.getElementById("terminalBody");

  const summaryCards = document.getElementById("summaryCards");
  const metricFetched = document.getElementById("metricFetched");
  const metricEligible = document.getElementById("metricEligible");
  const metricSynced = document.getElementById("metricSynced");
  const metricMetaOnly = document.getElementById("metricMetaOnly");
  const metricAlready = document.getElementById("metricAlready");
  const metricFailed = document.getElementById("metricFailed");
  const commitBanner = document.getElementById("commitBanner");
  const commitLink = document.getElementById("commitLink");

  const tableSearch = document.getElementById("tableSearch");
  const tableCountBadge = document.getElementById("tableCountBadge");
  const tableBody = document.getElementById("submissionsTableBody");
  const tableSortSelect = document.getElementById("tableSortSelect");
  const loadAllDayOneBtn = document.getElementById("loadAllDayOneBtn");
  const dayOneBadge = document.getElementById("dayOneBadge");

  let loadedSubmissions = [];
  let userRepos = [];
  let currentSortOrder = "asc"; // Default: Day 1 first

  // Theme Toggle
  themeToggleBtn.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const nextTheme = currentTheme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", nextTheme);
  });

  // Flow Switcher Notice
  flowRadios.forEach(radio => {
    radio.addEventListener("change", (e) => {
      if (e.target.value === "own") {
        flowNotice.className = "alert alert-info";
        flowNotice.innerHTML = "<strong>Flow A Active:</strong> Submissions and full source code will be synchronized where Codeforces permits.";
      } else {
        flowNotice.className = "alert alert-info";
        flowNotice.innerHTML = "<strong>Flow B Active (Public Account):</strong> Submission metadata, problem URLs, and details will be imported. Source code is not scraped to honor platform policies.";
      }
    });
  });

  // Codeforces Verify Handle
  cfVerifyBtn.addEventListener("click", async () => {
    const handle = cfHandleInput.value.trim();
    if (!handle) {
      alert("Please enter a Codeforces handle");
      return;
    }

    cfVerifyBtn.disabled = true;
    cfVerifyBtn.innerText = "Verifying...";

    try {
      const resp = await fetch("/api/codeforces/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handle })
      });
      const data = await resp.json();

      if (!resp.ok || !data.success) {
        alert(data.error || "User not found on Codeforces");
        return;
      }

      cfProfileHandle.innerText = data.handle;
      cfRankBadge.innerText = data.rank || "unranked";
      cfRatingBadge.innerText = data.rating ? `Rating: ${data.rating}` : "Unrated";
      cfAvatar.src = data.avatar || "https://userpic.codeforces.org/no-avatar.jpg";
      cfProfileBanner.classList.remove("hidden");

      // Auto preview from Day 1
      loadPreview(handle, null, "asc");
    } catch (err) {
      alert("Error verifying handle: " + err.message);
    } finally {
      cfVerifyBtn.disabled = false;
      cfVerifyBtn.innerText = "Verify";
    }
  });

  // GitHub Connect
  ghConnectBtn.addEventListener("click", async () => {
    const token = ghTokenInput.value.trim();
    if (!token) {
      alert("Please enter a GitHub Personal Access Token");
      return;
    }

    ghConnectBtn.disabled = true;
    ghConnectBtn.innerText = "Connecting...";

    try {
      const resp = await fetch("/api/github/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
      });
      const data = await resp.json();

      if (!resp.ok || !data.success) {
        alert(data.error || "GitHub authentication failed");
        return;
      }

      ghUsername.innerText = data.user.login;
      ghAvatar.src = data.user.avatarUrl || "";
      ghUserBanner.classList.remove("hidden");

      userRepos = data.repos || [];
      ghRepoSelect.innerHTML = '<option value="">Select a repository...</option>';
      userRepos.forEach(r => {
        const opt = document.createElement("option");
        opt.value = r.fullName;
        opt.innerText = `${r.fullName} ${r.isPrivate ? "(private)" : ""}`;
        if (!r.canPush) {
          opt.disabled = true;
          opt.innerText += " (No write access)";
        }
        ghRepoSelect.appendChild(opt);
      });
      ghRepoSelect.disabled = false;
    } catch (err) {
      alert("Error connecting to GitHub: " + err.message);
    } finally {
      ghConnectBtn.disabled = false;
      ghConnectBtn.innerText = "Connect";
    }
  });

  // Repo Select -> Load branches
  ghRepoSelect.addEventListener("change", async () => {
    const fullRepo = ghRepoSelect.value;
    if (!fullRepo) {
      ghBranchSelect.disabled = true;
      return;
    }

    const [owner, repo] = fullRepo.split("/");
    const token = ghTokenInput.value.trim();

    try {
      const resp = await fetch(`/api/github/branches?owner=${owner}&repo=${repo}&token=${encodeURIComponent(token)}`);
      const data = await resp.json();
      if (data.success && data.branches) {
        ghBranchSelect.innerHTML = "";
        data.branches.forEach(b => {
          const opt = document.createElement("option");
          opt.value = b;
          opt.innerText = b;
          if (b === "main" || b === "master") opt.selected = true;
          ghBranchSelect.appendChild(opt);
        });
        ghBranchSelect.disabled = false;
      }
    } catch (err) {
      console.warn("Could not load branches", err);
    }
  });

  // Load Submissions Preview
  async function loadPreview(handle, customLimit = null, sortOrder = null) {
    const h = handle || cfHandleInput.value.trim();
    if (!h) {
      alert("Please enter a Codeforces handle first");
      return;
    }

    const isOwn = document.querySelector('input[name="flowMode"]:checked').value === "own";
    const sort = sortOrder || tableSortSelect.value || currentSortOrder;
    let limitQuery = "";

    if (customLimit !== null) {
      limitQuery = customLimit ? `&limit=${customLimit}` : "&limit=0";
    } else if (filterLimit.value) {
      limitQuery = `&limit=${parseInt(filterLimit.value)}`;
    }

    previewBtn.disabled = true;
    previewBtn.innerText = "Loading...";

    try {
      const resp = await fetch(`/api/codeforces/submissions?handle=${encodeURIComponent(h)}${limitQuery}&is_own_account=${isOwn}&sort=${sort}`);
      const data = await resp.json();
      if (data.success && data.submissions) {
        loadedSubmissions = data.submissions;
        renderSubmissionsTable(loadedSubmissions);
      }
    } catch (err) {
      console.error("Preview load error", err);
    } finally {
      previewBtn.disabled = false;
      previewBtn.innerText = "Preview Submissions";
    }
  }

  previewBtn.addEventListener("click", () => {
    loadPreview();
  });

  // Fetch All Submissions from Day 1
  loadAllDayOneBtn.addEventListener("click", () => {
    loadAllDayOneBtn.disabled = true;
    loadAllDayOneBtn.innerText = "Fetching All...";
    loadPreview(null, 0, "asc").finally(() => {
      loadAllDayOneBtn.disabled = false;
      loadAllDayOneBtn.innerText = "📥 All from Day 1";
    });
  });

  // Table Sort Order Change
  tableSortSelect.addEventListener("change", () => {
    currentSortOrder = tableSortSelect.value;
    if (loadedSubmissions && loadedSubmissions.length > 0) {
      if (currentSortOrder === "asc") {
        loadedSubmissions.sort((a, b) => (a.creationTimeSeconds || 0) - (b.creationTimeSeconds || 0));
        dayOneBadge.innerText = "From Day 1";
      } else {
        loadedSubmissions.sort((a, b) => (b.creationTimeSeconds || 0) - (a.creationTimeSeconds || 0));
        dayOneBadge.innerText = "Latest First";
      }
      renderSubmissionsTable(loadedSubmissions);
    } else {
      loadPreview(null, null, currentSortOrder);
    }
  });

  // Render Submissions Table
  function renderSubmissionsTable(items) {
    if (!items || items.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="8" class="empty-state">No submissions found matching criteria.</td></tr>`;
      tableCountBadge.innerText = "0 items";
      return;
    }

    tableCountBadge.innerText = `${items.length} items`;
    tableBody.innerHTML = items.map((sub, index) => {
      const prob = sub.problem || {};
      const verdict = sub.verdict || "PENDING";
      const isOk = verdict === "OK";
      const verdictBadgeClass = isOk ? "badge-success" : (verdict.includes("WRONG") ? "badge-danger" : "badge-warning");
      const statusBadge = sub.status ? `<span class="badge ${getStatusClass(sub.status)}">${sub.status}</span>` : `<span class="badge">READY</span>`;
      const sourceBadge = sub.sourceAvailable ? `<span class="badge badge-success">Available</span>` : `<span class="badge badge-warning">Metadata</span>`;
      
      const subTime = sub.creationTimeSeconds ? new Date(sub.creationTimeSeconds * 1000) : (sub.createdAtUtc ? new Date(sub.createdAtUtc) : null);
      const dateDisplay = subTime ? `${subTime.toISOString().slice(0, 10)} ${subTime.toISOString().slice(11, 16)}` : 'N/A';
      const dayNum = currentSortOrder === "asc" ? `#${index + 1}` : `#${items.length - index}`;

      return `
        <tr>
          <td><span class="badge ${index === 0 && currentSortOrder === 'asc' ? 'badge-info' : ''}">${dayNum}</span></td>
          <td><a href="${sub.submissionUrl || '#'}" target="_blank" class="problem-link">#${sub.id || sub.submissionId}</a></td>
          <td><span class="path-code" title="${subTime ? subTime.toUTCString() : ''}">${dateDisplay}</span></td>
          <td>
            <a href="${sub.problemUrl || '#'}" target="_blank" class="problem-link">
              <strong>${prob.index || sub.problemIndex || ''}</strong>. ${prob.name || sub.problemName || 'Problem'}
            </a>
            ${sub.contestName || sub.contestId ? `<small class="helper-text">${sub.contestName || ('Contest ' + sub.contestId)}</small>` : ''}
          </td>
          <td><span class="badge ${verdictBadgeClass}">${verdict}</span></td>
          <td>${sub.programmingLanguage || sub.language || 'Code'}</td>
          <td>${sourceBadge}</td>
          <td>${statusBadge}</td>
        </tr>
      `;
    }).join("");
  }

  function getStatusClass(status) {
    switch (status) {
      case "SYNCED": return "badge-success";
      case "SOURCE_UNAVAILABLE": return "badge-warning";
      case "ALREADY_SYNCED": return "badge-info";
      case "FAILED": return "badge-danger";
      default: return "";
    }
  }

  // Filter Table Search
  tableSearch.addEventListener("input", () => {
    const q = tableSearch.value.toLowerCase();
    const filtered = loadedSubmissions.filter(s => {
      const p = s.problem || {};
      return (
        (s.id && String(s.id).includes(q)) ||
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.index && p.index.toLowerCase().includes(q)) ||
        (s.programmingLanguage && s.programmingLanguage.toLowerCase().includes(q)) ||
        (s.verdict && s.verdict.toLowerCase().includes(q))
      );
    });
    renderSubmissionsTable(filtered);
  });

  // Start Sync
  syncNowBtn.addEventListener("click", async () => {
    const handle = cfHandleInput.value.trim();
    const token = ghTokenInput.value.trim();
    const fullRepo = ghRepoSelect.value;
    const branch = ghBranchSelect.value || "main";
    const destDir = ghDestDir.value.trim() || "codeforces";

    if (!handle) {
      alert("Please enter a Codeforces handle.");
      return;
    }
    if (!token || !fullRepo) {
      alert("Please connect GitHub and select a destination repository.");
      return;
    }

    const [owner, repo] = fullRepo.split("/");
    const isOwn = document.querySelector('input[name="flowMode"]:checked').value === "own";

    const payload = {
      handle,
      githubToken: token,
      repoOwner: owner,
      repoName: repo,
      branch,
      destinationDir: destDir,
      isOwnAccount: isOwn,
      filter: {
        verdictMode: filterVerdict.value,
        limit: filterLimit.value ? parseInt(filterLimit.value) : null,
        contestId: filterContest.value ? parseInt(filterContest.value) : null,
        problemIndex: filterProblemIndex.value.trim() || null,
        language: filterLanguage.value.trim() || null,
        problemTag: filterTag.value.trim() || null,
        onlyNew: filterOnlyNew.checked,
      },
      async: true
    };

    // UI state
    syncNowBtn.disabled = true;
    syncBtnSpinner.classList.remove("hidden");
    progressCard.classList.remove("hidden");
    summaryCards.classList.add("hidden");
    commitBanner.classList.add("hidden");
    terminalBody.innerHTML = "";
    progressBar.style.width = "0%";
    progressPercentText.innerText = "0%";
    syncStatusBadge.innerText = "RUNNING";
    syncStatusBadge.className = "badge badge-running";

    try {
      const resp = await fetch("/api/codeforces/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (!resp.ok || !data.success) {
        alert(data.error || "Failed to start sync");
        syncNowBtn.disabled = false;
        syncBtnSpinner.classList.add("hidden");
        return;
      }

      const jobId = data.jobId;
      pollJobProgress(jobId);
    } catch (err) {
      alert("Sync error: " + err.message);
      syncNowBtn.disabled = false;
      syncBtnSpinner.classList.add("hidden");
    }
  });

  // Poll Job Progress
  function pollJobProgress(jobId) {
    const interval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/codeforces/sync/${jobId}`);
        const data = await resp.json();
        if (!data.success || !data.job) return;

        const job = data.job;
        progressBar.style.width = `${job.progressPercent}%`;
        progressPercentText.innerText = `${job.progressPercent}%`;
        currentStepText.innerText = job.currentStep || "Processing...";

        // Update terminal log
        if (job.logs && job.logs.length) {
          terminalBody.innerHTML = job.logs.map(l => `
            <div class="terminal-line">
              <span class="term-time">${new Date(l.time).toLocaleTimeString()}</span>
              <span>${l.message}</span>
            </div>
          `).join("");
          terminalBody.scrollTop = terminalBody.scrollHeight;
        }

        if (job.status !== "RUNNING") {
          clearInterval(interval);
          syncNowBtn.disabled = false;
          syncBtnSpinner.classList.add("hidden");

          syncStatusBadge.innerText = job.status;
          syncStatusBadge.className = job.status === "COMPLETED" ? "badge badge-success" : (job.status === "PARTIAL" ? "badge badge-warning" : "badge badge-danger");

          if (job.result) {
            displaySummary(job.result);
          }
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }, 1000);
  }

  function displaySummary(result) {
    summaryCards.classList.remove("hidden");
    metricFetched.innerText = result.totalFetched || 0;
    metricEligible.innerText = result.eligibleSubmissions || 0;
    metricSynced.innerText = result.successfullySynced || 0;
    metricMetaOnly.innerText = result.sourceUnavailable || 0;
    metricAlready.innerText = result.alreadySynced || 0;
    metricFailed.innerText = result.failed || 0;

    if (result.commitUrl) {
      commitLink.href = result.commitUrl;
      commitBanner.classList.remove("hidden");
    }

    if (result.items && result.items.length) {
      loadedSubmissions = result.items;
      renderSubmissionsTable(result.items);
    }
  }
});
