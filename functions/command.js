import { errorText, text } from "./common.js";
import { routeFromCommand } from "./routes.js";
import { runNoteCommand } from "./storage.js";
import { triggerNote } from "./trigger.js";

export function registerNoteCommand(api) {
  api.registerCommand({
    name: "note",
    description: "Store a deterministic note.",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx) => {
      const message = text(ctx.args);
      try {
        const result = await runNoteCommand(ctx.config, ctx.sessionKey, message, {
          channel: text(ctx.channelId) || text(ctx.channel),
          account_id: text(ctx.accountId),
          sender_id: text(ctx.senderId),
          message_id: "",
        });
        triggerNote(api, result, routeFromCommand(ctx), ctx.config, ctx.sessionKey);
        return { text: result.reply || "" };
      } catch (error) {
        api.logger.error?.(`NOTE command failed: ${errorText(error)}`);
        return { text: "❌ Note processing failed." };
      }
    },
  });
}
