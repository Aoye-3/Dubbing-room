import { describe, expect, it } from "vitest";
import { backendErrorMessage, classifyBackendError } from "./errors";

describe("classifyBackendError", () => {
  it.each([
    ["model_version_mismatch", "Configuration"],
    ["text_emotion_memory_insufficient", "Memory"],
    ["cancelled", "Cancelled"],
    ["reference_truncated", "Truncation"],
    ["worker_failed", "Inference"],
  ])("classifies %s as %s while retaining details", (code, category) => {
    expect(classifyBackendError({ message: "failed", code, type: "BackendFailure", details: { hint: "x" } })).toEqual({
      category, message: "failed", code, type: "BackendFailure", details: { hint: "x" },
    });
  });

  it("extracts the message from a structured plain-object rejection", () => {
    expect(backendErrorMessage({ code: "validation_error", message: "Speaker is required" })).toBe("Speaker is required");
  });
});
