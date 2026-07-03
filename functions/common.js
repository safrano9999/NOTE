export function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function enabled(name, fallback = false) {
  const value = text(process.env[name]).toLowerCase();
  return value ? ["1", "true", "yes", "on"].includes(value) : fallback;
}

export function errorText(error) {
  return error instanceof Error ? error.message : String(error);
}
