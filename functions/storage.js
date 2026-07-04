import { agentIdFromSession, pythonCommand, storeScript, workspaceFor } from "./paths.js";
import { run } from "./process.js";

export async function runNote(config, sessionKey, payload) {
  const input = {
    ...payload,
    workspace: workspaceFor(config, agentIdFromSession(sessionKey)),
    session_key: sessionKey,
    timestamp: Date.now(),
  };
  const output = await run(pythonCommand(), [storeScript], { input: JSON.stringify(input) });
  return JSON.parse(output);
}

export function saveNote(config, sessionKey, payload) {
  return runNote(config, sessionKey, { ...payload, action: "save" });
}

export function runNoteCommand(config, sessionKey, message, payload) {
  return runNote(config, sessionKey, { ...payload, action: "command", message });
}
