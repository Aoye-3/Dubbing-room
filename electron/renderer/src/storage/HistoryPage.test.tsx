import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { apiClient } from "../shared/api/client";
import { HistoryPage } from "./HistoryPage";

const t = ((key: string) => key) as never;

describe("HistoryPage", () => {
  it("shows messages from structured plain-object rejections on a legacy data action", async () => {
    vi.spyOn(apiClient, "listGenerations").mockRejectedValue({ code: "history_unavailable", message: "History could not be loaded" });
    render(<HistoryPage generations={[]} appDataState="ready" appDataError="" reload={vi.fn()} t={t} />);
    await userEvent.click(screen.getByRole("button", { name: "trashTab" }));
    expect(await screen.findByText("History could not be loaded")).toBeInTheDocument();
  });

  it("shows IndexTTS-2.5 identity, effective parameters, and warnings", () => {
    render(<HistoryPage generations={[{
      id: "generation-1",
      input_text: "Hello",
      control_instruction: JSON.stringify({ params: { language: "EN", duration_factor: 1.25 } }),
      source_mode: "indextts2-performance",
      status: "succeeded",
      model_id: "IndexTTS-2.5",
      model_version: "2.5",
      warnings: [{ code: "reference_truncated", message: "Reference truncated to 15 seconds." }],
      description: "Take 1",
      output_audio_path: "data/take.wav",
      is_favorite: false,
      created_at: "2026-08-12T00:00:00Z",
    } as never]} appDataState="ready" appDataError="" reload={vi.fn()} t={t} />);
    expect(screen.getByText(/IndexTTS-2.5.*2.5/)).toBeInTheDocument();
    expect(screen.getByText(/EN.*1.25/)).toBeInTheDocument();
    expect(screen.getByText("Reference truncated to 15 seconds.")).toBeInTheDocument();
    expect(document.querySelector("audio")).toBeNull();
  });
});
