import { spawn } from "child_process";
import fs from "fs";
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

export function runAuthLogin(onData) {
  return spawnPython(["auth", "login"], onData);
}

export function runPurchase(onData, checkout = false) {
  const args = ["run", "--recipe", "recipes/current-week.json"];
  if (checkout) args.push("--checkout");
  return spawnPython(args, onData);
}
