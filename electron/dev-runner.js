const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const electronPath = require("electron");

const rendererHost = "127.0.0.1";
const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const commandShell = process.env.ComSpec || "cmd.exe";

function pipeOutput(child) {
  child.stdout?.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr?.on("data", (chunk) => process.stderr.write(chunk));
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
    server.listen(port, rendererHost);
  });
}

async function pickRendererPort() {
  const explicitPort = parsePortEnv("VITE_RENDERER_PORT");
  if (explicitPort !== null) {
    if (await canListen(explicitPort)) {
      return explicitPort;
    }
    throw new Error(`VITE_RENDERER_PORT=${explicitPort} is already in use on ${rendererHost}.`);
  }

  for (let port = 17888; port <= 17999; port += 1) {
    if (await canListen(port)) {
      return port;
    }
  }
  throw new Error("No available renderer port in range 17888-17999.");
}

function waitForRenderer(rendererUrl, timeoutMs = 120000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(rendererUrl, (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error(`Renderer did not start at ${rendererUrl}`));
          return;
        }
        setTimeout(tick, 500);
      });
      req.setTimeout(1000, () => {
        req.destroy();
        setTimeout(tick, 500);
      });
    };
    tick();
  });
}

const viteCommand = process.platform === "win32" ? commandShell : npmCmd;
const viteArgs =
  process.platform === "win32" ? ["/d", "/s", "/c", npmCmd, "run", "renderer:dev"] : ["run", "renderer:dev"];

async function main() {
  const rendererPort = await pickRendererPort();
  const rendererUrl = `http://${rendererHost}:${rendererPort}`;
  const childEnv = {
    ...process.env,
    VITE_RENDERER_PORT: String(rendererPort),
    VITE_DEV_SERVER_URL: rendererUrl,
  };

  const vite = spawn(viteCommand, viteArgs, {
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
    env: childEnv,
  });
  pipeOutput(vite);

  vite.on("exit", (code) => {
    if (code !== 0) {
      process.exit(code ?? 1);
    }
  });

  waitForRenderer(rendererUrl)
    .then(() => {
    const electron = spawn(electronPath, ["."], {
      stdio: ["ignore", "pipe", "pipe"],
      shell: false,
      env: childEnv,
    });
    pipeOutput(electron);

    electron.on("exit", (code) => {
      vite.kill();
      process.exit(code ?? 0);
    });
  })
  .catch((error) => {
    console.error(error);
    vite.kill();
    process.exit(1);
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
