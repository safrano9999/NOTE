import { noteDirectory, pythonCommand, storeScript } from "./paths.js";
import { run } from "./process.js";

export async function saveNote(config, sessionKey, payload) {
  const input = {
    ...payload,
    note_path: noteDirectory(config, sessionKey),
    timestamp: Date.now(),
  };
  const output = await run(pythonCommand(), [storeScript], { input: JSON.stringify(input) });
  return { ...input, ...JSON.parse(output) };
}

export async function showNotes(config, sessionKey, hours) {
  const input = {
    action: "show",
    note_path: noteDirectory(config, sessionKey),
    ...(hours === undefined ? {} : { hours }),
  };
  const output = await run(pythonCommand(), [storeScript], { input: JSON.stringify(input) });
  return JSON.parse(output).text;
}
