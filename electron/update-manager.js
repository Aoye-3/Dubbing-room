const { execFile } = require("child_process");
const fs = require("fs");
const path = require("path");

const PROTECTED_PATHS = [
  "data/app/",
  "data/app/app.sqlite3",
  "data/runtimes/",
  "data/model-cache/",
  "data/pytest-tmp/",
  ".venv/",
  "node_modules/",
  ".npm-cache/",
  ".local-ffmpeg/",
  "*.log",
  "lora/",
  "checkpoints/",
  "logs/",
  "runs/",
  "tensorboard/",
];

function runGit(projectDir, args, options = {}) {
  return new Promise((resolve) => {
    execFile(
      "git",
      args,
      {
        cwd: projectDir,
        windowsHide: true,
        timeout: options.timeoutMs ?? 120000,
        maxBuffer: options.maxBuffer ?? 1024 * 1024,
      },
      (error, stdout, stderr) => {
        resolve({
          ok: !error,
          exitCode: typeof error?.code === "number" ? error.code : 0,
          stdout: String(stdout || "").trim(),
          stderr: String(stderr || "").trim(),
          args,
        });
      },
    );
  });
}

function normalizeRepositoryUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }

  const sshMatch = raw.match(/^git@github\.com[:/](.+?)(?:\.git)?\/?$/i);
  if (sshMatch) {
    return `github.com/${stripGitSuffix(sshMatch[1]).toLowerCase()}`;
  }

  try {
    const parsed = new URL(raw);
    if (parsed.hostname.toLowerCase() !== "github.com") {
      return "";
    }
    return `github.com/${stripGitSuffix(parsed.pathname).replace(/^\/+/, "").toLowerCase()}`;
  } catch {
    return "";
  }
}

function stripGitSuffix(value) {
  return String(value || "").replace(/\/+$/, "").replace(/\.git$/i, "");
}

function isSafeBranchName(branch) {
  const value = String(branch || "").trim();
  return (
    /^[A-Za-z0-9._/-]+$/.test(value) &&
    !value.includes("..") &&
    !value.startsWith("-") &&
    !value.startsWith("/") &&
    !value.endsWith("/") &&
    !value.endsWith(".")
  );
}

async function getRequiredGit(projectDir, args, summary) {
  const result = await runGit(projectDir, args);
  if (!result.ok) {
    throw new Error(`${summary}: ${result.stderr || result.stdout || `git ${args.join(" ")}`}`);
  }
  return result.stdout;
}

async function getCurrentBranch(projectDir) {
  return getRequiredGit(projectDir, ["branch", "--show-current"], "Could not read current branch");
}

async function getOriginUrl(projectDir) {
  return getRequiredGit(projectDir, ["remote", "get-url", "origin"], "Could not read origin remote");
}

async function getCurrentCommit(projectDir) {
  return getRequiredGit(projectDir, ["rev-parse", "HEAD"], "Could not read current commit");
}

async function getDirtyTrackedFiles(projectDir) {
  const status = await getRequiredGit(
    projectDir,
    ["status", "--porcelain", "--untracked-files=no"],
    "Could not read git status",
  );
  if (!status) {
    return [];
  }
  return status
    .split(/\r?\n/)
    .map((line) => line.slice(3).trim())
    .filter(Boolean);
}

async function getRemoteCommit(projectDir, branch) {
  const ref = `refs/remotes/origin/${branch}`;
  const result = await runGit(projectDir, ["rev-parse", "--verify", ref]);
  return result.ok ? result.stdout : "";
}

async function getAheadBehind(projectDir, branch) {
  const ref = `refs/remotes/origin/${branch}`;
  const result = await runGit(projectDir, ["rev-list", "--left-right", "--count", `HEAD...${ref}`]);
  if (!result.ok || !result.stdout) {
    return { ahead: 0, behind: 0 };
  }
  const [ahead, behind] = result.stdout.split(/\s+/).map((item) => Number(item) || 0);
  return { ahead, behind };
}

async function getProtectedPathChecks(projectDir) {
  const checks = [];
  for (const protectedPath of PROTECTED_PATHS) {
    const check = await runGit(projectDir, ["check-ignore", "--quiet", "--", protectedPath], { timeoutMs: 30000 });
    checks.push({
      path: protectedPath,
      ignored: check.exitCode === 0,
      exists: fs.existsSync(path.join(projectDir, protectedPath.replace(/\*.*$/, ""))),
      classification: protectedPath.startsWith("data/app") ? "user-data" : "local-runtime",
    });
  }
  return checks;
}

function buildBlockers({
  branch,
  currentBranch,
  originUrl,
  repositoryUrl,
  dirtyTrackedFiles,
  protectedPaths,
}) {
  const blockers = [];
  const normalizedOrigin = normalizeRepositoryUrl(originUrl);
  const normalizedRequested = normalizeRepositoryUrl(repositoryUrl || originUrl);

  if (!isSafeBranchName(branch)) {
    blockers.push("Target branch name is not allowed.");
  }
  if (!normalizedOrigin || normalizedOrigin !== normalizedRequested) {
    blockers.push("GitHub URL must match the current origin repository.");
  }
  if (currentBranch !== branch) {
    blockers.push(`Current branch must be ${branch} before applying updates.`);
  }
  if (dirtyTrackedFiles.length > 0) {
    blockers.push("Tracked working tree changes must be committed before updating.");
  }
  const unprotected = protectedPaths.filter((item) => !item.ignored);
  if (unprotected.length > 0) {
    blockers.push(`Protected local paths are not ignored: ${unprotected.map((item) => item.path).join(", ")}`);
  }
  return blockers;
}

async function getUpdateStatus(projectDir, options = {}) {
  const branch = String(options.branch || "main").trim();
  const [currentBranch, currentCommit, originUrl, dirtyTrackedFiles, protectedPaths] = await Promise.all([
    getCurrentBranch(projectDir),
    getCurrentCommit(projectDir),
    getOriginUrl(projectDir),
    getDirtyTrackedFiles(projectDir),
    getProtectedPathChecks(projectDir),
  ]);
  const [upstreamCommit, counts] = await Promise.all([
    isSafeBranchName(branch) ? getRemoteCommit(projectDir, branch) : Promise.resolve(""),
    isSafeBranchName(branch) ? getAheadBehind(projectDir, branch) : Promise.resolve({ ahead: 0, behind: 0 }),
  ]);
  const blockers = buildBlockers({
    branch,
    currentBranch,
    originUrl,
    repositoryUrl: options.repositoryUrl,
    dirtyTrackedFiles,
    protectedPaths,
  });

  return {
    state: blockers.length > 0 ? "blocked" : counts.behind > 0 ? "updateAvailable" : "upToDate",
    repositoryUrl: options.repositoryUrl || originUrl,
    remoteUrl: originUrl,
    currentBranch,
    targetBranch: branch,
    currentCommit,
    upstreamCommit,
    ahead: counts.ahead,
    behind: counts.behind,
    dirtyTrackedFiles,
    protectedPaths,
    blockers,
    log: [],
  };
}

async function preflightUpdate(projectDir, options = {}) {
  return getUpdateStatus(projectDir, options);
}

async function fetchUpdate(projectDir, options = {}) {
  const branch = String(options.branch || "main").trim();
  const before = await getUpdateStatus(projectDir, options);
  if (before.blockers.some((blocker) => !blocker.startsWith("Current branch must be"))) {
    return {
      ok: false,
      state: "blocked",
      summary: "Fetch blocked by preflight.",
      status: before,
      log: before.blockers,
      error: before.blockers.join(" "),
    };
  }
  if (!isSafeBranchName(branch)) {
    return {
      ok: false,
      state: "blocked",
      summary: "Fetch blocked by invalid branch.",
      status: before,
      log: [],
      error: "Target branch name is not allowed.",
    };
  }

  const refspec = `+refs/heads/${branch}:refs/remotes/origin/${branch}`;
  const fetchResult = await runGit(projectDir, ["fetch", "origin", refspec], { timeoutMs: 300000, maxBuffer: 2 * 1024 * 1024 });
  const after = await getUpdateStatus(projectDir, options);
  return {
    ok: fetchResult.ok,
    state: fetchResult.ok ? after.state : "failed",
    summary: fetchResult.ok ? "Fetched origin successfully." : "Fetch failed.",
    status: after,
    log: [fetchResult.stdout, fetchResult.stderr].filter(Boolean),
    error: fetchResult.ok ? "" : fetchResult.stderr || fetchResult.stdout || "Fetch failed.",
  };
}

async function applyUpdate(projectDir, options = {}) {
  const branch = String(options.branch || "main").trim();
  const before = await getUpdateStatus(projectDir, options);
  if (before.blockers.length > 0) {
    return {
      ok: false,
      state: "blocked",
      summary: "Update blocked by preflight.",
      status: before,
      log: before.blockers,
      error: before.blockers.join(" "),
    };
  }
  if (before.behind === 0) {
    return {
      ok: true,
      state: "upToDate",
      summary: "Already up to date.",
      status: before,
      log: [],
      error: "",
    };
  }

  const ref = `refs/remotes/origin/${branch}`;
  const mergeResult = await runGit(projectDir, ["merge", "--ff-only", ref], { timeoutMs: 300000, maxBuffer: 2 * 1024 * 1024 });
  const after = await getUpdateStatus(projectDir, options);
  return {
    ok: mergeResult.ok,
    state: mergeResult.ok ? "succeeded" : "blocked",
    summary: mergeResult.ok ? "Fast-forward update applied. Restart AppShell to load new code." : "Fast-forward update could not be applied.",
    status: after,
    log: [mergeResult.stdout, mergeResult.stderr].filter(Boolean),
    error: mergeResult.ok ? "" : mergeResult.stderr || mergeResult.stdout || "Fast-forward merge failed.",
  };
}

module.exports = {
  PROTECTED_PATHS,
  applyUpdate,
  fetchUpdate,
  getUpdateStatus,
  normalizeRepositoryUrl,
  preflightUpdate,
  isSafeBranchName,
};
