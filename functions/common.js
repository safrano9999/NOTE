export function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function errorText(error) {
  return error instanceof Error ? error.message : String(error);
}
