import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { registerNoteCommand } from "./functions/command.js";
import { registerDirectNoteHandler } from "./functions/direct.js";

const configSchema = {
  type: "object",
  additionalProperties: false,
  properties: {},
};

export default definePluginEntry({
  id: "note",
  name: "NOTE",
  description: "Stores deterministic notes without an AI model call.",
  configSchema,
  register(api) {
    registerNoteCommand(api);
    registerDirectNoteHandler(api);
  },
});
