import { text } from "./common.js";

export function isDummyProvider(ctx) {
  return text(ctx.modelProviderId).toLowerCase() === "dummy";
}

export function isNotesModel(ctx) {
  return isDummyProvider(ctx) && text(ctx.modelId).toLowerCase() === "note";
}

export function isSlashCommand(message) {
  return /^\//.test(text(message));
}

export function shouldStoreDirectNote(ctx, message) {
  return isNotesModel(ctx) && Boolean(text(message)) && !isSlashCommand(message);
}
