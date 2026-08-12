import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SettingsPage } from "./routes";
import { apiClient } from "../shared/api/client";

describe("SettingsPage", () => {
  it("saves the edited IndexTTS runtime profile for the next worker", async () => {
    const profile = { precision: "auto" as const, allow_text_emotion: true, use_cuda_kernel: false, use_deepspeed: false, use_accel: false, use_torch_compile: false };
    vi.spyOn(apiClient, "getRuntimeBackends").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "getIndexTTS2RuntimeProfile").mockResolvedValue({ profile, effective_precision: "bf16", warnings: [], capability: {} });
    const save = vi.spyOn(apiClient, "saveIndexTTS2RuntimeProfile").mockResolvedValue({ profile: { ...profile, precision: "fp32" }, effective_precision: "fp32", warnings: [], capability: {} });
    render(<SettingsPage status={{ state: "ready", message: "", detail: "" }} shellState={null} language="en" setLanguage={vi.fn()} t={((key: string) => key) as never} />);
    await userEvent.selectOptions(await screen.findByLabelText("Precision"), "fp32");
    await userEvent.click(screen.getByLabelText("CUDA kernel"));
    await userEvent.click(screen.getByRole("button", { name: "Save runtime profile" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith({ ...profile, precision: "fp32", use_cuda_kernel: true }));
    expect(await screen.findByText(/saved for the next worker/i)).toBeInTheDocument();
  });

  it("shows a structured runtime-profile load error instead of an endless loading state", async () => {
    vi.spyOn(apiClient, "getRuntimeBackends").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "getIndexTTS2RuntimeProfile").mockRejectedValue({ code: "runtime_profile_missing", message: "Runtime profile is unavailable" });
    render(<SettingsPage status={{ state: "ready", message: "", detail: "" }} shellState={null} language="en" setLanguage={vi.fn()} t={((key: string) => key) as never} />);
    expect(await screen.findByText("Runtime profile is unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Loading runtime profile…")).not.toBeInTheDocument();
  });

  it("keeps edited checkbox state and shows a structured save error", async () => {
    const profile = { precision: "auto" as const, allow_text_emotion: true, use_cuda_kernel: false, use_deepspeed: false, use_accel: false, use_torch_compile: false };
    vi.spyOn(apiClient, "getRuntimeBackends").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "getIndexTTS2RuntimeProfile").mockResolvedValue({ profile, effective_precision: "fp32", warnings: [], capability: {} });
    vi.spyOn(apiClient, "saveIndexTTS2RuntimeProfile").mockRejectedValue({ code: "validation_error", message: "Acceleration settings conflict" });
    render(<SettingsPage status={{ state: "ready", message: "", detail: "" }} shellState={null} language="en" setLanguage={vi.fn()} t={((key: string) => key) as never} />);
    const acceleration = await screen.findByLabelText("Acceleration");
    await userEvent.click(acceleration);
    await userEvent.click(screen.getByRole("button", { name: "Save runtime profile" }));
    expect(await screen.findByText("Acceleration settings conflict")).toBeInTheDocument();
    expect(acceleration).toBeChecked();
  });
});
