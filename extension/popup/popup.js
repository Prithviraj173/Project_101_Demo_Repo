document.addEventListener("DOMContentLoaded", async () => {
  const ghToken = document.getElementById("ghToken");
  const ghRepo = document.getElementById("ghRepo");
  const ghBranch = document.getElementById("ghBranch");
  const ghDir = document.getElementById("ghDir");
  const organizeMode = document.getElementById("organizeMode");
  const saveBtn = document.getElementById("saveBtn");
  const statusAlert = document.getElementById("statusAlert");

  // Load existing settings
  const settings = await chrome.storage.local.get(["ghToken", "ghRepo", "ghBranch", "ghDir", "organizeMode"]);
  if (settings.ghToken) ghToken.value = settings.ghToken;
  if (settings.ghRepo) ghRepo.value = settings.ghRepo;
  if (settings.ghBranch) ghBranch.value = settings.ghBranch;
  if (settings.ghDir) ghDir.value = settings.ghDir;
  if (settings.organizeMode) organizeMode.value = settings.organizeMode;

  saveBtn.addEventListener("click", async () => {
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
      saveBtn.innerText = "Save Settings";

      if (res && res.success) {
        await chrome.storage.local.set({
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
    statusAlert.innerText = msg;
    statusAlert.className = `status-alert ${type}`;
    statusAlert.classList.remove("hidden");
    setTimeout(() => {
      statusAlert.classList.add("hidden");
    }, 4000);
  }
});
