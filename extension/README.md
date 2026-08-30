# Codeforces to GitHub Sync — Chrome Extension

A Manifest V3 browser extension that runs directly on `codeforces.com` to synchronize your submissions into your GitHub repository in 1 click, automatically sorted by contest, rating, and topic tags.

---

## 🚀 How to Install Locally

1. Open your browser (Google Chrome, Brave, Microsoft Edge, or Chromium).
2. Navigate to:
   ```
   chrome://extensions
   ```
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** (top-left button).
5. Select the `extension/` folder from this repository:
   ```
   C:\Users\prith\Desktop\Project-101\extension
   ```
6. The extension is now installed and active!

---

## ⚡ How to Use

1. Click on the extension icon in your browser toolbar.
2. Enter your **GitHub Personal Access Token (PAT)** and your **Target Repository** (e.g. `Prithviraj173/Project_101_Demo_Repo`).
3. Choose your repository organization layout:
   - 🌟 **All Layouts**: Generates By-Rating (`by-rating/1400/`), By-Tag (`by-tag/dp/`), By-Contest (`by-contest/`), and a dynamic `README.md` table!
   - ⭐ **By Rating**: Groups solutions cleanly by difficulty rating.
   - 🏷️ **By Topic Tag**: Groups solutions by algorithm topics.
4. Click **Save Settings**.
5. Open any submission on [codeforces.com](https://codeforces.com) — a **⚡ Sync to GitHub** button will appear above your code box to push with 1 click!
