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

async function getOrCreateRepo(token, repoName = "Codeforces-Solutions") {
  const headers = {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28"
  };

  const userRes = await fetch(`${GITHUB_API_URL}/user`, { headers });
  if (!userRes.ok) throw new Error("GitHub Authentication failed");
  const user = await userRes.json();
  const owner = user.login;

  const repoRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}`, { headers });
  if (repoRes.ok) {
    return { owner, repoName, fullName: `${owner}/${repoName}` };
  }

  // Create repository
  const createRes = await fetch(`${GITHUB_API_URL}/user/repos`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      name: repoName,
      description: `Automated Codeforces Solutions Archive — Topic-wise and Rating-wise from Day 1`,
      private: false,
      auto_init: true
    })
  });

  if (!createRes.ok) {
    const err = await createRes.json().catch(() => ({}));
    throw new Error(err.message || "Failed to create GitHub repository");
  }

  return { owner, repoName, fullName: `${owner}/${repoName}` };
}

// Full Sync from Day 1 (Accepted Solutions Only)
async function syncAllAcceptedFromDayOne({ token, handle, repoName = "Codeforces-Solutions", organizeMode = "ALL" }) {
  const { owner, fullName } = await getOrCreateRepo(token, repoName);
  const branch = "main";
  const baseDir = "codeforces";

  // Fetch all Codeforces submissions from Day 1
  const cfRes = await fetch(`https://codeforces.com/api/user.status?handle=${encodeURIComponent(handle)}&from=1&count=10000`);
  const cfData = await cfRes.json();
  if (cfData.status !== "OK") {
    throw new Error(cfData.comment || "Failed to fetch submissions from Codeforces");
  }

  // Filter ONLY Accepted solutions (verdict == "OK")
  const rawSubs = cfData.result || [];
  const acceptedSubs = rawSubs.filter(s => s.verdict === "OK");

  if (acceptedSubs.length === 0) {
    return { success: true, count: 0, message: "No accepted submissions found.", repoUrl: `https://github.com/${fullName}` };
  }

  const headers = {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28"
  };

  // Get branch HEAD
  const refRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/ref/heads/${branch}`, { headers });
  let headSha;
  let baseTreeSha;

  if (refRes.ok) {
    const refData = await refRes.json();
    headSha = refData.object.sha;
    const commitRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/commits/${headSha}`, { headers });
    const commitData = await commitRes.json();
    baseTreeSha = commitData.tree.sha;
  }

  const treeEntries = [];
  const processedProblems = new Set();
  const ratingMap = {};
  const tagMap = {};

  for (const s of acceptedSubs) {
    const prob = s.problem || {};
    const pKey = `${s.contestId || 'set'}_${prob.index || 'A'}`;
    if (processedProblems.has(pKey)) continue; // Keep newest accepted submission per problem
    processedProblems.add(pKey);

    const lang = s.programmingLanguage || "C++";
    const ext = getExtension(lang);
    const probIndex = sanitizeSegment(prob.index || "A");
    const probName = sanitizeSegment(prob.name || "Problem");
    const contestName = sanitizeSegment(`Contest-${s.contestId || 'set'}`);
    const probFolder = `${probIndex}-${probName}`;
    const solFilename = `solution.${ext}`;

    const r = prob.rating || 0;
    const ratingKey = r > 0 ? String(r).padStart(4, "0") : "unrated";
    ratingMap[ratingKey] = (ratingMap[ratingKey] || 0) + 1;

    const tags = prob.tags && prob.tags.length ? prob.tags : ["general"];
    for (const t of tags) {
      tagMap[t] = (tagMap[t] || 0) + 1;
    }

    const header = `// Problem: ${prob.index}. ${prob.name}\n// Contest: ${s.contestId}\n// Rating: ${prob.rating || 'Unrated'}\n// Tags: ${(prob.tags || []).join(', ')}\n// Verdict: OK (Accepted)\n// Date: ${new Date(s.creationTimeSeconds * 1000).toUTCString()}\n\n`;
    const sourceCode = header + `// Accepted Solution for Problem ${prob.index}. ${prob.name}\n// View details: https://codeforces.com/contest/${s.contestId}/submission/${s.id}\n`;
    const metaJson = JSON.stringify({
      id: s.id,
      contestId: s.contestId,
      problem: prob,
      verdict: "OK",
      language: lang,
      dateUtc: new Date(s.creationTimeSeconds * 1000).toISOString()
    }, null, 2);

    // Add layout destinations with inline content
    if (organizeMode === "ALL" || organizeMode === "CONTEST") {
      const p = `${baseDir}/by-contest/${s.contestId}-${contestName}/${probFolder}`;
      treeEntries.push({ path: `${p}/${solFilename}`, mode: "100644", type: "blob", content: sourceCode });
      treeEntries.push({ path: `${p}/metadata.json`, mode: "100644", type: "blob", content: metaJson });
    }

    if (organizeMode === "ALL" || organizeMode === "RATING") {
      const p = `${baseDir}/by-rating/${ratingKey}/${probFolder}`;
      treeEntries.push({ path: `${p}/${solFilename}`, mode: "100644", type: "blob", content: sourceCode });
      treeEntries.push({ path: `${p}/metadata.json`, mode: "100644", type: "blob", content: metaJson });
    }

    if (organizeMode === "ALL" || organizeMode === "TAG") {
      for (const tag of tags) {
        const tagFolder = sanitizeSegment(tag, "general");
        const p = `${baseDir}/by-tag/${tagFolder}/${probFolder}`;
        treeEntries.push({ path: `${p}/${solFilename}`, mode: "100644", type: "blob", content: sourceCode });
        treeEntries.push({ path: `${p}/metadata.json`, mode: "100644", type: "blob", content: metaJson });
      }
    }
  }

  // Create README.md summary index
  let readme = `# Codeforces Solutions Archive — @${handle}\n\n`;
  readme += `> Auto-generated archive of **${processedProblems.size}** unique Accepted Codeforces problems solved from **Day 1**.\n\n`;
  readme += `## 📊 Solutions by Rating\n| Rating | Solved Count | Folder Link |\n| :---: | :---: | :--- |\n`;
  for (const rKey of Object.keys(ratingMap).sort()) {
    const dName = rKey !== "unrated" && !isNaN(parseInt(rKey)) ? `⭐ ${parseInt(rKey)}` : "Unrated";
    readme += `| **${dName}** | ${ratingMap[rKey]} | [\`${rKey}\`](./${baseDir}/by-rating/${rKey}/) |\n`;
  }
  readme += `\n## 🏷️ Solutions by Topic / Tag\n| Tag | Solved Count | Folder Link |\n| :--- | :---: | :--- |\n`;
  for (const tKey of Object.keys(tagMap).sort((a, b) => tagMap[b] - tagMap[a])) {
    const tClean = tKey.replace(/\s+/g, '-');
    readme += `| \`${tKey}\` | ${tagMap[tKey]} | [\`${tKey}\`](./${baseDir}/by-tag/${tClean}/) |\n`;
  }

  treeEntries.push({ path: `README.md`, mode: "100644", type: "blob", content: readme });

  // Create tree
  const treeRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/trees`, {
    method: "POST",
    headers,
    body: JSON.stringify({ base_tree: baseTreeSha, tree: treeEntries })
  });
  const newTree = await treeRes.json();

  // Create commit
  const commitRes = await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/commits`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message: `Initial Sync: Import ${processedProblems.size} Accepted solutions for @${handle} from Day 1`,
      tree: newTree.sha,
      parents: headSha ? [headSha] : []
    })
  });
  const newCommit = await commitRes.json();

  // Update ref
  await fetch(`${GITHUB_API_URL}/repos/${owner}/${repoName}/git/refs/heads/${branch}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ sha: newCommit.sha, force: true })
  });

  return {
    success: true,
    count: processedProblems.size,
    repoUrl: `https://github.com/${fullName}`,
    commitUrl: newCommit.html_url || `https://github.com/${fullName}/commit/${newCommit.sha}`
  };
}

// Message Router
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "SYNC_SUBMISSION") {
    commitSubmissionToGitHub(request.payload)
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === "SYNC_ALL_FROM_DAY_ONE") {
    syncAllAcceptedFromDayOne(request.payload)
      .then(res => sendResponse(res))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
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
