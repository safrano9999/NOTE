import { enabled, errorText, text } from "./common.js";
import { shouldStoreDirectNote } from "./model.js";
import { routeFromAgentHook } from "./routes.js";
import { saveNote } from "./storage.js";
import { initialFeedback, triggerNote } from "./trigger.js";

export function registerDirectNoteHandler(api) {
  api.on("before_agent_reply", async (event, ctx) => {
    const message = text(event.cleanedBody);
    if (!shouldStoreDirectNote(ctx, message)) return;
    try {
      const note = await saveNote(api.runtime.config.current(), ctx.sessionKey, {
        message,
        channel: text(ctx.channel) || text(ctx.messageProvider),
        account_id: "",
        sender_id: text(ctx.senderId),
        message_id: "",
      });
      const triggered = triggerNote(api, note, routeFromAgentHook(ctx));
      return {
        handled: true,
        reply: { text: initialFeedback(triggered) },
        reason: "note saved",
      };
    } catch (error) {
      api.logger.error?.(`NOTE direct save failed: ${errorText(error)}`);
      return {
        handled: true,
        reply: enabled("NOTE_FEEDBACK", true) ? { text: "❌ Note save failed." } : undefined,
        reason: "note save failed",
      };
    }
  });
}
