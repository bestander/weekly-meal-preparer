import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const SESSION_PATH = path.join(ROOT, "data", "session.json");
const SESSION_MAX_AGE_DAYS = 25;

const VENV_PYTHON = path.join(ROOT, ".venv", "bin", "python");

function pythonCmd() {
  return fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";
}

export function getSessionStatus() {
  if (!fs.existsSync(SESSION_PATH)) {
    return { status: "missing", savedAt: null, ageDays: null };
  }

  const data = JSON.parse(fs.readFileSync(SESSION_PATH, "utf8"));
  const savedAt = data.saved_at;
  const saved = new Date(savedAt);
  const ageDays = Math.floor((Date.now() - saved.getTime()) / (24 * 60 * 60 * 1000));
  const valid = ageDays < SESSION_MAX_AGE_DAYS;

  return {
    status: valid ? "valid" : "expired",
    savedAt,
    ageDays,
    maxAgeDays: SESSION_MAX_AGE_DAYS,
  };
}

export function spawnPython(args, onData) {
  return new Promise((resolve, reject) => {
    const proc = spawn(pythonCmd(), ["-m", "purchasing", ...args], {
      cwd: ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    const chunks = { stdout: "", stderr: "" };

    proc.stdout.on("data", (buf) => {
      const text = buf.toString();
      chunks.stdout += text;
      onData?.("stdout", text);
    });

    proc.stderr.on("data", (buf) => {
      const text = buf.toString();
      chunks.stderr += text;
      onData?.("stderr", text);
    });

    proc.on("close", (code) => {
      resolve({ code, ...chunks });
    });

    proc.on("error", reject);
  });
}

function spawnPythonJson(args, onEvent) {
  return new Promise((resolve, reject) => {
    const proc = spawn(pythonCmd(), ["-m", "purchasing", ...args], {
      cwd: ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    let buffer = "";
    let lastDone = null;
    let stderr = "";

    proc.stdout.on("data", (buf) => {
      buffer += buf.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const event = JSON.parse(trimmed);
          onEvent?.(event);
          if (event.type === "done") lastDone = event;
          if (event.type === "error") {
            reject(new Error(event.message || "Purchase step failed"));
          }
        } catch {
          // ignore non-JSON lines
        }
      }
    });

    proc.stderr.on("data", (buf) => {
      stderr += buf.toString();
      onEvent?.({ type: "log", stream: "stderr", text: buf.toString() });
    });

    proc.on("close", (code) => {
      if (buffer.trim()) {
        try {
          const event = JSON.parse(buffer.trim());
          onEvent?.(event);
          if (event.type === "done") lastDone = event;
        } catch {
          // ignore
        }
      }
      if (code !== 0 && !lastDone) {
        reject(new Error(stderr.trim() || `Process exited with code ${code}`));
        return;
      }
      resolve({ code, result: lastDone, stderr });
    });

    proc.on("error", reject);
  });
}

export function runAuthLogin(onData) {
  return spawnPython(["auth", "login"], onData);
}

export function runResolve(onEvent) {
  return spawnPythonJson(
    ["web", "resolve", "--recipe", "recipes/current-week.json"],
    onEvent,
  );
}

export function runFinish(approvalData, checkout = false, onEvent) {
  const tmpPath = path.join(os.tmpdir(), `meal-approval-${Date.now()}.json`);
  fs.writeFileSync(tmpPath, JSON.stringify(approvalData));
  const args = ["web", "finish", "--approval", tmpPath];
  if (checkout) args.push("--checkout");
  return spawnPythonJson(args, onEvent).finally(() => {
    try {
      fs.unlinkSync(tmpPath);
    } catch {
      // ignore
    }
  });
}

export function runSearchOne(ingredient, onEvent) {
  return spawnPythonJson(["web", "search", ingredient], onEvent);
}
