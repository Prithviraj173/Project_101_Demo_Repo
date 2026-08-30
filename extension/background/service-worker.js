// Background service worker for Codeforces to GitHub Sync Extension

const GITHUB_API_URL = "https://api.github.com";

// Language to extension mapping
const EXT_MAP = {
  "c++": "cpp",
  "gnu c++": "cpp",
  "python": "py",
  "pypy": "py",
  "java": "java",
  "kotlin": "kt",
  "rust": "rs",
  "go": "go",
  "c#": "cs",
  "javascript": "js",
  "typescript": "ts"
};

function getExtension(lang) {
  if (!lang) return "txt";
  const l = lang.toLowerCase();
  for (const [k, v] of Object.entries(EXT_MAP)) {
    if (l.includes(k)) return v;
  }
  return "txt";
}

function sanitizeSegment(str, def = "item") {
  if (!str) return def;
  return str.replace(/[\x00-\x1f\\/:*?"<>|\r\n\t\[\]]+/g, "-").replace(/[\s\-]+/g, "-").replace(/^[\.\-_]+|[\.\-_]+$/g, "") || def;
}

// GitHub API Client inside Extension
async function commitSubmissionToGitHub({ token, repo, branch = "main", baseDir = "codeforces", submission, organizeMode = "ALL" }) {
  const [owner, repoName] = repo.split("/");
  const headers = {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28"
  };

  // 1. Get branch HEAD commit
  const refRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/ref/heads/${branch}`, { headers });
  if (!refRes.ok) {
    const errData = await refRes.json().catch(() => ({}));
    throw new Error(errData.message || `Could not find branch '${branch}'`);
  }
  const refData = await refRes.json();
  const headSha = refData.object.sha;

  // 2. Get base tree
  const commitRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/commits/${headSha}`, { headers });
  const commitData = await commitRes.json();
  const baseTreeSha = commitData.tree.sha;

  // 3. Prepare solution & metadata content
  const lang = submission.language || "C++";
  const ext = getExtension(lang);
  const probIndex = sanitizeSegment(submission.problemIndex || "A");
  const probName = sanitizeSegment(submission.problemName || "Problem");
  const contestName = sanitizeSegment(submission.contestName || `Contest-${submission.contestId || 'set'}`);
  const probFolder = `${probIndex}-${probName}`;
  const solFilename = `solution.${ext}`;

  const header = `// Problem: ${submission.problemIndex}. ${submission.problemName}\n// Contest: ${submission.contestName || submission.contestId}\n// URL: ${submission.problemUrl || ''}\n// Language: ${lang}\n// Verdict: ${submission.verdict || 'OK'}\n\n`;
  const fullSource = header + (submission.sourceCode || "// Source code placeholder\n");
  const metadataJson = JSON.stringify(submission, null, 2);

  // 4. Create blobs
  const srcBlobRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/blobs`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content: fullSource, encoding: "utf-8" })
  });
  const srcBlob = await srcBlobRes.json();

  const metaBlobRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/blobs`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content: metadataJson, encoding: "utf-8" })
  });
  const metaBlob = await metaBlobRes.json();

  // 5. Build tree entries across layouts (by-contest, by-rating, by-tag)
  const treeEntries = [];

  // Contest layout
  if (organizeMode === "ALL" || organizeMode === "CONTEST") {
    const p = `${baseDir}/by-contest/${submission.contestId || 'gym'}-${contestName}/${probFolder}`;
    treeEntries.push({ path: `${p}/${solFilename}`, mode: "100644", type: "blob", sha: srcBlob.sha });
    treeEntries.push({ path: `${p}/metadata.json`, mode: "100644", type: "blob", sha: metaBlob.sha });
  }

  // Rating layout (sorted by rating!)
  if (organizeMode === "ALL" || organizeMode === "RATING") {
    const ratingStr = submission.rating ? String(submission.rating).padStart(4, "0") : "unrated";
    const p = `${baseDir}/by-rating/${ratingStr}/${probFolder}`;
    treeEntries.push({ path: `${p}/${solFilename}`, mode: "100644", type: "blob", sha: srcBlob.sha });
    treeEntries.push({ path: `${p}/metadata.json`, mode: "100644", type: "blob", sha: metaBlob.sha });
  }

  // Tag layout
  if (organizeMode === "ALL" || organizeMode === "TAG") {
    const tags = submission.tags && submission.tags.length ? submission.tags : ["general"];
    for (const tag of tags) {
      const tagFolder = sanitizeSegment(tag, "general");
      const p = `${baseDir}/by-tag/${tagFolder}/${probFolder}`;
      treeEntries.push({ path: `${p}/${solFilename}`, mode: "100644", type: "blob", sha: srcBlob.sha });
      treeEntries.push({ path: `${p}/metadata.json`, mode: "100644", type: "blob", sha: metaBlob.sha });
    }
  }

  // 6. Create tree
  const treeRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/trees`, {
    method: "POST",
    headers,
    body: JSON.stringify({ base_tree: baseTreeSha, tree: treeEntries })
  });
  const newTree = await treeRes.json();

  // 7. Create commit
  const newCommitRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/commits`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message: `Sync Codeforces ${submission.problemIndex}: ${submission.problemName} (${submission.verdict || 'OK'})`,
      tree: newTree.sha,
      parents: [headSha]
    })
  });
  const newCommit = await newCommitRes.json();

  // 8. Update ref
  await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/refs/heads/${branch}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ sha: newCommit.sha, force: false })
  });

  return {
    success: true,
    commitSha: newCommit.sha,
    commitUrl: newCommit.html_url || `https://github.com/${owner}/${repoName}/commit/${newCommit.sha}`
  };
}

// Message Router
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "SYNC_SUBMISSION") {
    commitSubmissionToGitHub(request.payload)
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open for async response
  }

  if (request.action === "VERIFY_GITHUB") {
    fetch(`${GITHUB_API_URL}/user`, {
      headers: {
        "Authorization": `Bearer ${request.token}`,
        "Accept": "application/vnd.github+json"
      }
    })
      .then(res => res.json())
      .then(user => sendResponse({ success: Boolean(user && user.login), user }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
