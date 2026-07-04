import { text } from "./common.js";

export function messageFromEvent(event) {
  const hasMedia = Array.isArray(event?.mediaPaths) && event.mediaPaths.length > 0;
  const message = hasMedia ? text(event?.userText) : text(event?.cleanedBody);
  const cleaned = message
    .split(/\r?\n/)
    .filter((line) => !/^\[media attached(?:\s+\d+\/\d+)?:[^\]]+\]$/i.test(line.trim()))
    .join("\n")
    .replace(/<media:[^>]+>/gi, "")
    .trim();
  return hasMedia ? cleaned.replace(/^\[[^\]\n]+\]\s+[^:\n]+:\s*/, "").trim() : cleaned;
}

export function mediaFromEvent(event) {
  const paths = Array.isArray(event?.mediaPaths) ? event.mediaPaths : [];
  const types = Array.isArray(event?.mediaTypes) ? event.mediaTypes : [];
  return paths
    .map((sourcePath, index) => ({
      source_path: text(sourcePath),
      mime_type: text(types[index]),
      workspace_dir: text(event?.mediaWorkspaceDir),
    }))
    .filter((item) => item.source_path);
}

export function contactsFromEvent(event) {
  const entries = Array.isArray(event?.structuredContext) ? event.structuredContext : [];
  return entries
    .filter((entry) => text(entry?.type).toLowerCase() === "contact")
    .map((entry) => ({
      label: text(entry?.label),
      source: text(entry?.source),
      payload: entry?.payload,
    }));
}

export function payloadFromEvent(event) {
  return {
    message: messageFromEvent(event),
    media: mediaFromEvent(event),
    contacts: contactsFromEvent(event),
    location: event?.location && typeof event.location === "object" ? event.location : null,
  };
}

export function hasInboundContent(payload) {
  return Boolean(payload.message || payload.media.length || payload.contacts.length || payload.location);
}
