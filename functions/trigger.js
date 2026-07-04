import { errorText } from "./common.js";
import { runNote } from "./storage.js";

export async function sendStatus(api, route, status) {
  if (!status || !route.channel || !route.target) return;
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

export function triggerNote(api, result, route, config, sessionKey) {
  if (!result.trigger || !result.note) return;
  void runNote(config, sessionKey, { action: "trigger", note: result.note })
    .then((triggerResult) => sendStatus(api, route, triggerResult.status))
    .catch((error) => {
      api.logger.error?.(`NOTE trigger failed: ${errorText(error)}`);
    });
}
