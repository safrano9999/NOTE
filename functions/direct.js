import { errorText, text } from "./common.js";
import { shouldStoreDirectNote } from "./model.js";
import { routeFromAgentHook } from "./routes.js";
import { saveNote } from "./storage.js";
import { triggerNote } from "./trigger.js";

export function registerDirectNoteHandler(api) {
  api.on("before_agent_reply", async (event, ctx) => {
    const message = text(event.cleanedBody);
    if (!shouldStoreDirectNote(ctx, message)) return;
    try {
      const config = api.runtime.config.current();
      const result = await saveNote(config, ctx.sessionKey, {
        message,
        channel: text(ctx.channel) || text(ctx.messageProvider),
        account_id: "",
        sender_id: text(ctx.senderId),
        message_id: "",
      });
      triggerNote(api, result, routeFromAgentHook(ctx), config, ctx.sessionKey);
      return {
        handled: true,
        reply: result.reply ? { text: result.reply } : undefined,
        reason: "note saved",
      };
    } catch (error) {
      api.logger.error?.(`NOTE direct save failed: ${errorText(error)}`);
      return {
        handled: true,
        reply: { text: "❌ Note processing failed." },
        reason: "note save failed",
      };
    }
  });
}
