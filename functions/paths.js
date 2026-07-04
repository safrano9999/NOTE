import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { text } from "./common.js";

export const pluginRoot = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
export const storeScript = path.join(pluginRoot, "note", "store.py");
const venvPython = path.join(pluginRoot, ".venv", "bin", "python");
const setupPython = path.join(pluginRoot, "scripts", "setup-python.sh");
let resolvedPython;

export function pythonCommand() {
  if (resolvedPython) return resolvedPython;
  if (!fs.existsSync(setupPython)) return fs.existsSync(venvPython) ? venvPython : "python3";
  const result = spawnSync(setupPython, { cwd: pluginRoot, encoding: "utf8" });
  if (result.status !== 0) throw new Error((result.stderr || "Python setup failed").trim());
  resolvedPython = result.stdout.trim().split(/\r?\n/).at(-1) || "python3";
  return resolvedPython;
}

export function agentIdFromSession(sessionKey) {
  return text(sessionKey).match(/^agent:([^:]+):/i)?.[1] || "main";
}

export function workspaceFor(config, agentId) {
  const agent = Array.isArray(config?.agents?.list)
    ? config.agents.list.find((item) => text(item?.id).toLowerCase() === agentId.toLowerCase())
    : undefined;
  const configured = text(agent?.workspace) || text(config?.agents?.defaults?.workspace);
  return path.resolve(configured.replace(/^~(?=\/)/, os.homedir()) || path.join(os.homedir(), ".openclaw", "workspace"));
}
