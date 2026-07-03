import { enabled, errorText, text } from "./common.js";
import { routeFromCommand } from "./routes.js";
import { saveNote, showNotes } from "./storage.js";
import { initialFeedback, triggerNote } from "./trigger.js";

export function parseShowHours(message) {
  const match = text(message).match(/^show(?:\s+(\d+(?:[.,]\d+)?)h)?$/i);
  if (!match) return null;
  const hours = match[1] ? Number(match[1].replace(",", ".")) : undefined;
  return hours === undefined || (Number.isFinite(hours) && hours > 0) ? { hours } : { invalid: true };
}

export function registerNoteCommand(api) {
  api.registerCommand({
    name: "note",
    description: "Store a deterministic note.",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx) => {
      const message = text(ctx.args);
      if (!message) return { text: "Usage: /note <message>" };
      const show = parseShowHours(message);
      if (show) {
        if (show.invalid) return { text: "Usage: /note show [hours]h" };
        try {
          return { text: await showNotes(ctx.config, ctx.sessionKey, show.hours) };
        } catch (error) {
          api.logger.error?.(`NOTE show failed: ${errorText(error)}`);
          return { text: "❌ Note show failed." };
        }
      }
      if (/^show\b/i.test(message)) return { text: "Usage: /note show or /note show <hours>h" };
      try {
        const note = await saveNote(ctx.config, ctx.sessionKey, {
          message,
          channel: text(ctx.channelId) || text(ctx.channel),
          account_id: text(ctx.accountId),
          sender_id: text(ctx.senderId),
          message_id: "",
        });
        const triggered = triggerNote(api, note, routeFromCommand(ctx));
        return { text: initialFeedback(triggered) || "" };
      } catch (error) {
        api.logger.error?.(`NOTE save failed: ${errorText(error)}`);
        return { text: enabled("NOTE_FEEDBACK", true) ? "❌ Note save failed." : "" };
      }
    },
  });
}
