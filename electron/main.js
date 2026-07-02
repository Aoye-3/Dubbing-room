const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn, execFile } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const projectDir = path.resolve(__dirname, "..");
const backendHost = "127.0.0.1";
const defaultMainPort = 8808;
const defaultAppBackendPort = 8818;
let mainPort = defaultMainPort;
let mainUrl = localUrl(mainPort);
let appBackendPort = defaultAppBackendPort;
let appBackendUrl = localUrl(appBackendPort);
const outLogPath = path.join(projectDir, "voxcpm_webui.out.log");
const errLogPath = path.join(projectDir, "voxcpm_webui.err.log");
const appBackendOutLogPath = path.join(projectDir, "voxcpm_app_backend.out.log");
const appBackendErrLogPath = path.join(projectDir, "voxcpm_app_backend.err.log");
const shouldStartLegacyWebUI = process.env.VOXCPM_START_LEGACY_GRADIO === "1";
const appBackendPostTimeoutMs = 30 * 60 * 1000;
const appBackendStatusTimeoutMs = 10 * 1000;
const appServiceActions = new Set([
  "list-voices",
  "create-voice",
  "update-voice",
  "delete-voice",
  "list-generations",
  "create-generation",
  "mark-generation-running",
  "mark-generation-succeeded",
  "mark-generation-failed",
  "delete-generation",
]);

let mainWindow = null;
let legacyBackendProcess = null;
let appBackendProcess = null;
let isQuitting = false;
let lastStatus = { state: "starting", message: "Starting VoxCPM AppShell", detail: "" };

function localUrl(port) {
  return `http://${backendHost}:${port}`;
}

function refreshBackendUrls() {
  mainUrl = localUrl(mainPort);
  appBackendUrl = localUrl(appBackendPort);
}

function sendStatus(state, message, detail = "") {
  lastStatus = { state, message, detail };
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  mainWindow.webContents.send("status", lastStatus);
}

function pythonPath() {
  const venvPython = path.join(projectDir, ".venv", "Scripts", "python.exe");
  return fs.existsSync(venvPython) ? venvPython : "python";
}

function pythonEnv() {
  const localFfmpegDir = path.join(projectDir, ".local-ffmpeg");
  const env = {
    ...process.env,
    PYTHONPATH: [path.join(projectDir, "src"), process.env.PYTHONPATH || ""]
      .filter(Boolean)
      .join(path.delimiter),
  };
  if (fs.existsSync(path.join(localFfmpegDir, "ffmpeg.exe"))) {
    env.PATH = `${localFfmpegDir}${path.delimiter}${env.PATH || ""}`;
    env.IMAGEIO_FFMPEG_EXE = path.join(localFfmpegDir, "ffmpeg.exe");
  }
  return env;
}

function truncateLogs(stdoutPath, stderrPath) {
  fs.writeFileSync(stdoutPath, "", "utf8");
  fs.writeFileSync(stderrPath, "", "utf8");
}

function parsePortEnv(envName) {
  const value = process.env[envName];
  if (!value) {
    return null;
  }
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`${envName} must be a TCP port between 1 and 65535.`);
  }
  return port;
}

function canListen(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, backendHost);
  });
}

async function pickPort({ envName, defaultPort, endPort }) {
  const explicitPort = parsePortEnv(envName);
  if (explicitPort !== null) {
    if (await canListen(explicitPort)) {
      return explicitPort;
    }
    throw new Error(`${envName}=${explicitPort} is already in use on ${backendHost}.`);
  }

  for (let port = defaultPort; port <= endPort; port += 1) {
    if (await canListen(port)) {
      return port;
    }
  }
  throw new Error(`No available local port in range ${defaultPort}-${endPort}.`);
}

async function configureBackendPorts() {
  if (shouldStartLegacyWebUI) {
    mainPort = await pickPort({
      envName: "VOXCPM_LEGACY_WEBUI_PORT",
      defaultPort: defaultMainPort,
      endPort: 8899,
    });
  } else {
    appBackendPort = await pickPort({
      envName: "VOXCPM_APP_BACKEND_PORT",
      defaultPort: defaultAppBackendPort,
      endPort: 8899,
    });
  }
  refreshBackendUrls();
}

function isUrlReady(url) {
  return new Promise((resolve) => {
    const request = http.get(url, (response) => {
      response.resume();
      resolve(response.statusCode >= 200 && response.statusCode < 500);
    });
    request.on("error", () => resolve(false));
    request.setTimeout(1200, () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function waitForBackend(url, getProcess, timeoutMs = 180000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await isUrlReady(url)) {
      return true;
    }
    const processRef = getProcess();
    if (processRef && processRef.exitCode !== null) {
      return false;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

function startBackend() {
  if (legacyBackendProcess) {
    return;
  }

  truncateLogs(outLogPath, errLogPath);
  const py = pythonPath();
  const args = ["run_with_local_ffmpeg.py", "app.py", "--port", String(mainPort), "--device", "cuda"];
  const outLog = fs.openSync(outLogPath, "a");
  const errLog = fs.openSync(errLogPath, "a");

  sendStatus("starting", "Starting VoxCPM backend", `${py} ${args.join(" ")}`);
  legacyBackendProcess = spawn(py, args, {
    cwd: projectDir,
    windowsHide: true,
    stdio: ["ignore", outLog, errLog],
  });
  fs.closeSync(outLog);
  fs.closeSync(errLog);

  legacyBackendProcess.on("exit", (code, signal) => {
    if (!isQuitting) {
      sendStatus("exited", "Backend exited", `code=${code ?? ""} signal=${signal ?? ""}`);
    }
  });
  legacyBackendProcess.on("error", (error) => {
    sendStatus("failed", "Failed to launch backend", error.stack || String(error));
  });
}

function startAppBackend() {
  if (appBackendProcess) {
    return;
  }

  truncateLogs(appBackendOutLogPath, appBackendErrLogPath);
  const py = pythonPath();
  const args = [
    "-m",
    "voxcpm_app.backend_server",
    "--project-root",
    projectDir,
    "--port",
    String(appBackendPort),
    "--device",
    process.env.VOXCPM_APP_DEVICE || "cuda",
  ];
  const outLog = fs.openSync(appBackendOutLogPath, "a");
  const errLog = fs.openSync(appBackendErrLogPath, "a");

  sendStatus("starting", "Starting VoxCPM App backend", `${py} ${args.join(" ")}`);
  appBackendProcess = spawn(py, args, {
    cwd: projectDir,
    windowsHide: true,
    stdio: ["ignore", outLog, errLog],
    env: pythonEnv(),
  });
  fs.closeSync(outLog);
  fs.closeSync(errLog);

  appBackendProcess.on("exit", (code, signal) => {
    if (!isQuitting) {
      sendStatus("exited", "App backend exited", `code=${code ?? ""} signal=${signal ?? ""}`);
    }
  });
  appBackendProcess.on("error", (error) => {
    sendStatus("failed", "Failed to launch App backend", error.stack || String(error));
  });
}

function postAppBackendJson(route, payload = {}, timeoutMs = appBackendPostTimeoutMs) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload || {});
    const request = http.request(
      `${appBackendUrl}${route}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (response) => {
        let data = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          data += chunk;
        });
        response.on("end", () => {
          let parsed = {};
          try {
            parsed = data.trim() ? JSON.parse(data) : {};
          } catch (error) {
            reject(new Error(`Invalid backend JSON: ${error.message}\n${data}`));
            return;
          }
          if (response.statusCode < 200 || response.statusCode >= 300) {
            reject(new Error(parsed.error || `Backend returned ${response.statusCode}`));
            return;
          }
          resolve(parsed);
        });
      }
    );
    request.on("error", reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`App backend request timed out after ${timeoutMs}ms: ${route}`));
    });
    request.end(body, "utf8");
  });
}

function getAppBackendJson(route, timeoutMs = appBackendStatusTimeoutMs) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${appBackendUrl}${route}`, (response) => {
      let data = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        data += chunk;
      });
      response.on("end", () => {
        try {
          const parsed = data.trim() ? JSON.parse(data) : {};
          if (response.statusCode < 200 || response.statusCode >= 300) {
            reject(new Error(parsed.error || `Backend returned ${response.statusCode}`));
            return;
          }
          resolve(parsed);
        } catch (error) {
          reject(new Error(`Invalid backend JSON: ${error.message}\n${data}`));
        }
      });
    });
    request.on("error", reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`App backend request timed out after ${timeoutMs}ms: ${route}`));
    });
  });
}

function runAppService(action, payload = {}) {
  if (!appServiceActions.has(action)) {
    return Promise.reject(new Error(`Unsupported app service action: ${action}`));
  }

  if (!shouldStartLegacyWebUI) {
    return postAppBackendJson("/app-service", { action, payload });
  }

  return new Promise((resolve, reject) => {
    const child = spawn(
      pythonPath(),
      ["-m", "voxcpm_app.service_cli", action, "--project-root", projectDir],
      {
        cwd: projectDir,
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
        env: pythonEnv(),
      }
    );

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      let parsed = null;
      try {
        parsed = stdout.trim() ? JSON.parse(stdout) : {};
      } catch (error) {
        reject(new Error(`Invalid app service JSON: ${error.message}\n${stdout}\n${stderr}`));
        return;
      }

      if (code !== 0) {
        reject(new Error(parsed.error || stderr || `App service exited with code ${code}`));
        return;
      }
      resolve(parsed);
    });

    child.stdin.end(JSON.stringify(payload || {}), "utf8");
  });
}

function cleanupResidualBackends() {
  return new Promise((resolve) => {
    const escapedProject = projectDir.replace(/'/g, "''");
    const command = [
      "$rows = Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\"",
      `| Where-Object { $_.CommandLine -like '*${escapedProject.replace(/\\/g, "\\\\")}*app.py --port ${mainPort}*' -or $_.CommandLine -like '*app.py --port ${mainPort} --device cuda*' };`,
      "foreach ($row in $rows) { Stop-Process -Id $row.ProcessId -Force -ErrorAction SilentlyContinue }"
    ].join(" ");

    execFile(
      "powershell.exe",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
      { cwd: projectDir, windowsHide: true },
      () => resolve()
    );
  });
}

async function stopBackend() {
  isQuitting = true;

  if (legacyBackendProcess && legacyBackendProcess.exitCode === null) {
    legacyBackendProcess.kill();
  }
  legacyBackendProcess = null;

  if (appBackendProcess && appBackendProcess.exitCode === null) {
    appBackendProcess.kill();
  }
  appBackendProcess = null;

  if (shouldStartLegacyWebUI) {
    await cleanupResidualBackends();
  }
}

async function bootWebUI() {
  startBackend();
  sendStatus("starting", "Starting VoxCPM backend", mainUrl);

  const ready = await waitForBackend(mainUrl, () => legacyBackendProcess);
  if (!ready) {
    sendStatus("failed", "Failed to start WebUI", `Check logs:\n${outLogPath}\n${errLogPath}`);
    return;
  }

  sendStatus("ready", "VoxCPM WebUI is ready", mainUrl);
}

async function bootAppBackend() {
  startAppBackend();
  sendStatus("starting", "Starting VoxCPM App backend", appBackendUrl);

  const ready = await waitForBackend(`${appBackendUrl}/health`, () => appBackendProcess);
  if (!ready) {
    sendStatus("failed", "Failed to start App backend", `Check logs:\n${appBackendOutLogPath}\n${appBackendErrLogPath}`);
    return;
  }

  sendStatus("ready", "VoxCPM AppShell is ready", appBackendUrl);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1120,
    minHeight: 760,
    title: "VoxCPM",
    backgroundColor: "#101214",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.removeMenu();
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  const rendererUrl = process.env.VITE_DEV_SERVER_URL;
  if (rendererUrl) {
    mainWindow.loadURL(rendererUrl);
  } else {
    mainWindow.loadFile(path.join(projectDir, "dist", "renderer", "index.html"));
  }
}

ipcMain.handle("get-shell-state", () => ({
  appMode: shouldStartLegacyWebUI ? "legacy-webui-dev" : "app-shell",
  backendUrl: shouldStartLegacyWebUI ? mainUrl : appBackendUrl,
  mainPort: shouldStartLegacyWebUI ? mainPort : appBackendPort,
  legacyBackendUrl: mainUrl,
  appBackendUrl,
  projectDir,
  outLogPath,
  errLogPath,
  appBackendOutLogPath,
  appBackendErrLogPath,
  status: lastStatus,
}));

ipcMain.on("media-url", (event, projectRelativePath) => {
  event.returnValue = `${appBackendUrl}/media?path=${encodeURIComponent(projectRelativePath)}`;
});

ipcMain.handle("app-service", (_event, request) => {
  const action = request && typeof request.action === "string" ? request.action : "";
  const payload = request && typeof request.payload === "object" ? request.payload : {};
  return runAppService(action, payload);
});

ipcMain.handle("generate-audio", (_event, payload) => {
  return postAppBackendJson("/generate-audio", payload || {});
});

ipcMain.handle("generate-indextts2", (_event, payload) => {
  return postAppBackendJson("/indextts2/generate", payload || {});
});

ipcMain.handle("get-runtime-backends", () => {
  return getAppBackendJson("/runtime-backends");
});

ipcMain.handle("create-generation-job", (_event, payload) => {
  return postAppBackendJson("/generation-jobs", payload || {});
});

ipcMain.handle("list-generation-jobs", () => {
  return getAppBackendJson("/generation-jobs");
});

ipcMain.handle("get-generation-job", (_event, payload) => {
  return getAppBackendJson(`/generation-jobs/${encodeURIComponent(payload.id)}`);
});

ipcMain.handle("cancel-generation-job", (_event, payload) => {
  return postAppBackendJson(`/generation-jobs/${encodeURIComponent(payload.id)}/cancel`, {});
});

ipcMain.handle("retry-generation-job", (_event, payload) => {
  return postAppBackendJson(`/generation-jobs/${encodeURIComponent(payload.id)}/retry`, {});
});

ipcMain.handle("list-generation-takes", (_event, payload) => {
  return getAppBackendJson(`/generation-jobs/${encodeURIComponent(payload.job_id)}/takes`);
});

ipcMain.handle("select-generation-take", (_event, payload) => {
  return postAppBackendJson(`/generation-takes/${encodeURIComponent(payload.id)}/select`, {});
});

ipcMain.handle("select-audio-file", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select reference audio",
    properties: ["openFile"],
    filters: [
      { name: "Audio", extensions: ["wav", "mp3", "m4a", "flac", "ogg", "aac"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  const selectedPath = result.filePaths[0];
  return {
    path: selectedPath,
    name: path.basename(selectedPath),
  };
});

app.whenReady().then(async () => {
  await configureBackendPorts();
  createWindow();
  if (shouldStartLegacyWebUI) {
    bootWebUI().catch((error) => {
      sendStatus("failed", "Startup error", error.stack || String(error));
    });
    return;
  }
  bootAppBackend().catch((error) => {
    sendStatus("failed", "Startup error", error.stack || String(error));
  });
}).catch((error) => {
  const detail = error.stack || String(error);
  sendStatus("failed", "Startup error", detail);
  dialog.showErrorBox("VoxCPM startup failed", detail);
  app.quit();
});

app.on("before-quit", async (event) => {
  if (isQuitting) {
    return;
  }
  event.preventDefault();
  await stopBackend();
  app.quit();
});

app.on("window-all-closed", () => {
  app.quit();
});
