document.addEventListener("DOMContentLoaded", async () => {
  const cfHandle = document.getElementById("cfHandle");
  const ghToken = document.getElementById("ghToken");
  const ghRepo = document.getElementById("ghRepo");
  const ghBranch = document.getElementById("ghBranch");
  const ghDir = document.getElementById("ghDir");
  const organizeMode = document.getElementById("organizeMode");
  const saveBtn = document.getElementById("saveBtn");
  const syncAllBtn = document.getElementById("syncAllBtn");
  const statusAlert = document.getElementById("statusAlert");

  // Load existing settings
  const settings = await chrome.storage.local.get(["cfHandle", "ghToken", "ghRepo", "ghBranch", "ghDir", "organizeMode"]);
  if (settings.cfHandle) cfHandle.value = settings.cfHandle;
  if (settings.ghToken) ghToken.value = settings.ghToken;
  if (settings.ghRepo) ghRepo.value = settings.ghRepo;
  if (settings.ghBranch) ghBranch.value = settings.ghBranch;
  if (settings.ghDir) ghDir.value = settings.ghDir;
  if (settings.organizeMode) organizeMode.value = settings.organizeMode;

  // 1-Click Sync All from Day 1 (Accepted Only)
  syncAllBtn.addEventListener("click", async () => {
    const handle = cfHandle.value.trim();
    const token = ghToken.value.trim();
    const repoName = ghRepo.value.trim() || "Codeforces-Solutions";
    const mode = organizeMode.value;

    if (!handle || !token) {
      showAlert("Please enter your Codeforces Handle and GitHub Token.", "error");
      return;
    }

    syncAllBtn.disabled = true;
    saveBtn.disabled = true;
    syncAllBtn.innerText = "⏳ Auto-Creating Repo & Syncing...";
    showAlert("Connecting to GitHub & fetching all Accepted submissions from Day 1...", "info");

    chrome.runtime.sendMessage({
      action: "SYNC_ALL_FROM_DAY_ONE",
      payload: {
        token,
        handle,
        repoName,
        organizeMode: mode
      }
    }, async (res) => {
      syncAllBtn.disabled = false;
      saveBtn.disabled = false;
      syncAllBtn.innerText = "🚀 1-Click Sync All (Day 1 Accepted Only)";

      if (res && res.success) {
        // Save settings for future use
        await chrome.storage.local.set({
          cfHandle: handle,
          ghToken: token,
          ghRepo: repoName,
          ghBranch: "main",
          ghDir: "codeforces",
          organizeMode: mode
        });
        statusAlert.innerHTML = `
          ✅ <strong>Success!</strong> Synced ${res.count} Accepted problems from Day 1.<br/>
          <a href="${res.repoUrl}" target="_blank" style="color:#34d399; font-weight:700; text-decoration:underline;">View Your Repo on GitHub ↗</a>
        `;
        statusAlert.className = "status-alert success";
        statusAlert.classList.remove("hidden");
      } else {
        showAlert("Sync failed: " + (res ? res.error : "Unknown error"), "error");
      }
    });
  });

  saveBtn.addEventListener("click", async () => {
    const handle = cfHandle.value.trim();
    const token = ghToken.value.trim();
    const repo = ghRepo.value.trim();
    const branch = ghBranch.value.trim() || "main";
    const dir = ghDir.value.trim() || "codeforces";
    const mode = organizeMode.value;

    if (!token || !repo) {
      showAlert("Please enter both a GitHub token and repository name.", "error");
      return;
    }

    saveBtn.disabled = true;
    saveBtn.innerText = "Verifying with GitHub...";

    chrome.runtime.sendMessage({ action: "VERIFY_GITHUB", token }, async (res) => {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save Settings for In-Page Sync";

      if (res && res.success) {
        await chrome.storage.local.set({
          cfHandle: handle,
          ghToken: token,
          ghRepo: repo,
          ghBranch: branch,
          ghDir: dir,
          organizeMode: mode
        });
        showAlert(`Connected as @${res.user.login}! Settings saved.`, "success");
      } else {
        showAlert("GitHub Token verification failed. Please check your token.", "error");
      }
    });
  });

  function showAlert(msg, type) {
    statusAlert.innerHTML = msg;
    statusAlert.className = `status-alert ${type}`;
    statusAlert.classList.remove("hidden");
    if (type !== "success") {
      setTimeout(() => {
        statusAlert.classList.add("hidden");
      }, 5000);
    }
  }
});
