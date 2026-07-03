import { text } from "./common.js";

export function routeFromCommand(ctx) {
  return {
    channel: text(ctx.channelId) || text(ctx.channel),
    accountId: text(ctx.accountId),
    target: text(ctx.from) || text(ctx.to),
    threadId: ctx.messageThreadId,
  };
}

export function routeFromAgentHook(ctx) {
  return {
    channel: text(ctx.channel) || text(ctx.messageProvider),
    accountId: "",
    target: text(ctx.chatId) || text(ctx.channelId),
  };
}
