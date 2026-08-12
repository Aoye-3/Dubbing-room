export type BackendErrorShape = {
  message?: string;
  error?: string;
  code?: string;
  type?: string;
  details?: Record<string, unknown>;
};

export type BackendErrorCategory = "Configuration" | "Memory" | "Cancelled" | "Truncation" | "Inference";

export function backendErrorMessage(value: unknown): string {
  const source = isObject(value) ? value : {};
  return readString(source.message) || readString(source.error) || (value instanceof Error ? value.message : String(value));
}

export function classifyBackendError(value: unknown) {
  const source = isObject(value) ? value : {};
  const code = readString(source.code) || "worker_failed";
  let category: BackendErrorCategory = "Inference";
  if (/config|missing|version|asset/i.test(code)) category = "Configuration";
  else if (/memory|oom/i.test(code)) category = "Memory";
  else if (/cancel/i.test(code)) category = "Cancelled";
  else if (/truncat|max_mel/i.test(code)) category = "Truncation";
  return {
    category,
    message: backendErrorMessage(value),
    code,
    type: readString(source.type),
    details: isObject(source.details) ? source.details : {},
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}
