import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PerformanceDesk } from "./PerformanceDesk";
import { apiClient } from "../shared/api/client";
import type { GenerationJob, GenerationTake } from "../shared/types";

const job = { id: "job-1", status: "running", params: { language: "EN" }, error_summary: "" } as unknown as GenerationJob;
const take = { id: "take-1", job_id: "job-1", take_index: 1, label: "Take 1", status: "succeeded", params: { duration_factor: 1 }, output_asset: { path: "data/take.wav", duration_seconds: 1.2 }, warnings: [{ code: "reference_truncated", message: "Reference truncated to 15 seconds." }], is_selected: false, error_summary: "" } as unknown as GenerationTake;

afterEach(() => vi.useRealTimers());

describe("PerformanceDesk", () => {
  it("polls the current job and Takes and cleans up its interval", async () => {
    vi.useFakeTimers();
    vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue(job);
    vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [take] });
    const clear = vi.spyOn(window, "clearTimeout");
    const view = render(<PerformanceDesk jobId="job-1" onHistoryChanged={vi.fn()} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText("Take 1")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(apiClient.getGenerationJob).toHaveBeenCalledTimes(2);
    view.unmount();
    expect(clear).toHaveBeenCalled();
  });

  it("stops polling after the job reaches a terminal state", async () => {
    vi.useFakeTimers();
    vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue({ ...job, status: "succeeded" });
    vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [take] });
    render(<PerformanceDesk jobId="job-1" onHistoryChanged={vi.fn()} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getAllByText("succeeded").length).toBeGreaterThan(0);
    await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
    expect(apiClient.getGenerationJob).toHaveBeenCalledTimes(1);
  });

  it("selects a successful Take so it projects into History", async () => {
    vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue({ ...job, status: "succeeded" });
    vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [take] });
    vi.spyOn(apiClient, "selectGenerationTake").mockResolvedValue({ ...take, is_selected: true });
    const historyChanged = vi.fn();
    render(<PerformanceDesk jobId="job-1" onHistoryChanged={historyChanged} />);
    await userEvent.click(await screen.findByRole("button", { name: "Select Take 1" }));
    await waitFor(() => expect(historyChanged).toHaveBeenCalled());
    expect(apiClient.selectGenerationTake).toHaveBeenCalledWith({ id: "take-1" });
  });

  it("shows a partial Take failure while keeping successful Take actions available", async () => {
    const failedTake = { ...take, id: "take-2", take_index: 2, label: "Take 2", status: "failed", output_asset: null, error_summary: "worker_failed: GPU fault" } as GenerationTake;
    vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue({ ...job, status: "succeeded" });
    vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [take, failedTake] });
    render(<PerformanceDesk jobId="job-1" onHistoryChanged={vi.fn()} />);
    expect(await screen.findByText("worker_failed: GPU fault")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select Take 1" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Select Take 2" })).toBeDisabled();
  });

  it("saves and exports a completed Take", async () => {
    vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue({ ...job, status: "succeeded" });
    vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [take] });
    const createVoice = vi.spyOn(apiClient, "createVoice").mockResolvedValue({ id: "voice-2" } as never);
    const exportAudio = vi.spyOn(apiClient, "exportAudioFile").mockResolvedValue({ ok: true, canceled: false, path: "D:/Take 1.wav" });
    render(<PerformanceDesk jobId="job-1" onHistoryChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Save Take 1 to Voice Library" }));
    expect(createVoice).toHaveBeenCalledWith(expect.objectContaining({ source_audio_path: "data/take.wav", source_generation_id: take.legacy_generation_id }));
    await userEvent.click(screen.getByRole("button", { name: "Export Take 1" }));
    expect(exportAudio).toHaveBeenCalledWith({ project_relative_path: "data/take.wav", suggested_name: "Take 1.wav" });
  });

  it("renders structured action failures and prevents duplicate actions", async () => {
    vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue({ ...job, status: "succeeded" });
    vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [take] });
    let rejectSave!: (reason: unknown) => void;
    vi.spyOn(apiClient, "createVoice").mockImplementation(() => new Promise((_resolve, reject) => { rejectSave = reject; }));
    render(<PerformanceDesk jobId="job-1" onHistoryChanged={vi.fn()} />);
    const save = await screen.findByRole("button", { name: "Save Take 1 to Voice Library" });
    await userEvent.click(save);
    expect(save).toBeDisabled();
    rejectSave({ code: "voice_save_failed", message: "Voice could not be saved", details: { retryable: true } });
    expect(await screen.findByText(/Voice could not be saved/)).toBeInTheDocument();
    expect(save).toBeEnabled();
  });
});
