import fs from "node:fs";
import path from "node:path";
import { enabled, errorText, text } from "./common.js";
import { pluginRoot } from "./paths.js";
import { run } from "./process.js";

export function promptText() {
  const configured = text(process.env.NOTE_PROMPT) || "prompt_default.md";
  const promptPath = path.isAbsolute(configured) ? configured : path.join(pluginRoot, configured);
  return fs.readFileSync(promptPath, "utf8").trim();
}

export function triggerEnvironment(note) {
  return {
    NOTE_PROMPT: promptText(),
    NOTE_MESSAGE: note.message,
    NOTE_DATE: note.date,
    NOTE_TIME: note.time,
    NOTE_PATH: note.note_path,
    NOTE_CHANNEL: note.channel || "",
    NOTE_ACCOUNT_ID: note.account_id || "",
    NOTE_SENDER_ID: note.sender_id || "",
    NOTE_MESSAGE_ID: note.message_id || "",
  };
}

export function triggerConfigured() {
  return (text(process.env.NOTE_TRIGGER_TYPE).toLowerCase() || "none") !== "none"
    && Boolean(text(process.env.NOTE_TRIGGER));
}

export async function executeTrigger(note) {
  const type = text(process.env.NOTE_TRIGGER_TYPE).toLowerCase() || "none";
  const target = text(process.env.NOTE_TRIGGER);
  if (type === "none" || !target) return false;
  const env = triggerEnvironment(note);
  if (type === "cli") {
    await run("/bin/sh", ["-lc", target], { env });
    return true;
  }
  if (type === "webhook") {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        authorization: "Bearer $SHADOWED_N8N_TOKEN",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        prompt: env.NOTE_PROMPT,
        message: env.NOTE_MESSAGE,
        date: env.NOTE_DATE,
        time: env.NOTE_TIME,
        path: env.NOTE_PATH,
        channel: env.NOTE_CHANNEL,
        account_id: env.NOTE_ACCOUNT_ID,
        sender_id: env.NOTE_SENDER_ID,
        message_id: env.NOTE_MESSAGE_ID,
      }),
      signal: AbortSignal.timeout(300_000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return true;
  }
  throw new Error(`Unsupported NOTE_TRIGGER_TYPE: ${type}`);
}

export async function sendStatus(api, route, status) {
  if (!enabled("NOTE_FEEDBACK", true) || !route.channel || !route.target) return;
  const adapter = await api.runtime.channel.outbound.loadAdapter(route.channel);
  if (!adapter?.sendText) return;
  await adapter.sendText({
    cfg: api.runtime.config.current(),
    to: route.target,
    text: status,
    ...(route.accountId ? { accountId: route.accountId } : {}),
    ...(route.threadId !== undefined ? { threadId: route.threadId } : {}),
  });
}

export function triggerNote(api, note, route) {
  if (!triggerConfigured()) return false;
  void executeTrigger(note)
    .then(() => sendStatus(api, route, "✅ Trigger completed."))
    .catch((error) => {
      api.logger.error?.(`NOTE trigger failed: ${errorText(error)}`);
      return sendStatus(api, route, "❌ Trigger failed.");
    });
  return true;
}

export function initialFeedback(triggered) {
  if (!enabled("NOTE_FEEDBACK", true)) return undefined;
  return triggered ? "✅ Note saved.\nTrigger fired." : "✅ Note saved.";
}
