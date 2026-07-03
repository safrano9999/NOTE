import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { text } from "./common.js";

export const pluginRoot = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
export const storeScript = path.join(pluginRoot, "note", "store.py");
const venvPython = path.join(pluginRoot, ".venv", "bin", "python");

export function pythonCommand() {
  return fs.existsSync(venvPython) ? venvPython : (process.env.NOTE_PYTHON || "python3");
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

export function noteDirectory(config, sessionKey) {
  const configured = text(process.env.NOTE_PATH) || "./OBSIDIAN/NOTES/INBOX";
  return path.isAbsolute(configured)
    ? configured
    : path.resolve(workspaceFor(config, agentIdFromSession(sessionKey)), configured);
}

export function ensureFileDirectories(api) {
  if ((text(process.env.NOTE_DB_BACKEND) || "file").toLowerCase() !== "file") return;
  const config = api.runtime.config.current();
  const agents = Array.isArray(config?.agents?.list) && config.agents.list.length
    ? config.agents.list
    : [{ id: "main" }];
  for (const agent of agents) {
    fs.mkdirSync(noteDirectory(config, `agent:${text(agent.id) || "main"}:main`), { recursive: true });
  }
}
