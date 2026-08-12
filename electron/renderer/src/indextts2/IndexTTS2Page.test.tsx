import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IndexTTS2Page } from "./IndexTTS2Page";
import { apiClient } from "../shared/api/client";
import type { RuntimeBackendStatus } from "../shared/types";

const t = ((key: string) => key) as never;
const runtime = {
  backend_id: "indextts2", display_name: "IndexTTS-2.5", enabled: true,
  configured: true, loaded: false, busy: false, device: "cuda", last_error: "",
  capabilities: [], model_id: "IndexTTS-2.5", model_version: "2.5",
  supported_languages: ["ZH", "EN", "JA", "ES", "AR"], effective_precision: "bf16",
  text_emotion_enabled: true, warnings: [], paths: {},
} satisfies RuntimeBackendStatus;

beforeEach(() => {
  vi.spyOn(apiClient, "getRuntimeBackends").mockResolvedValue({ items: [runtime] });
  vi.spyOn(apiClient, "createGenerationJob").mockResolvedValue({ id: "job-1" } as never);
  vi.spyOn(apiClient, "getGenerationJob").mockResolvedValue(undefined);
  vi.spyOn(apiClient, "listGenerationTakes").mockResolvedValue({ items: [] });
});

function renderPage() {
  return render(<IndexTTS2Page appReady status={{ state: "ready", message: "ready", detail: "" }} voices={[{ id: "voice-1", display_name: "Narrator" } as never]} reload={vi.fn()} t={t} />);
}

describe("IndexTTS2Page", () => {
  it("shows required 2.5 inputs and language-specific annotation helpers", async () => {
    renderPage();
    expect(await screen.findByLabelText("Language")).toHaveValue("ZH");
    expect(screen.getByLabelText("Duration factor")).toHaveAttribute("min", "0.5");
    expect(screen.getByLabelText("Duration factor")).toHaveAttribute("max", "2");
    expect(screen.getByText(/15 seconds/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pinyin annotation helper/i })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Language"), "JA");
    expect(screen.getByRole("button", { name: /Kana annotation helper/i })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Language"), "ES");
    expect(screen.queryByText(/annotation helper/i)).not.toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("targetText"));
    expect(screen.getByRole("button", { name: "Quick preview" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generate multiple Takes" })).toBeDisabled();
  });

  it("renders mutually exclusive emotion controls and no loading flags", async () => {
    renderPage();
    await screen.findByText("IndexTTS-2.5 / cuda");
    await userEvent.selectOptions(await screen.findByLabelText("emotionMode"), "text_prompt");
    expect(screen.getByLabelText("emotionText")).toBeInTheDocument();
    expect(screen.getByText(/8 GB.*out of memory.*no fallback/i)).toBeInTheDocument();
    expect(screen.queryByText("emotionReference")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "advanced" }));
    expect(screen.queryByText("do_sample")).not.toBeInTheDocument();
    expect(screen.queryByText("use_cuda_kernel")).not.toBeInTheDocument();
    expect(screen.getByLabelText("text_normalization")).toBeInTheDocument();
    expect(screen.queryByLabelText("use_random")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("emotionMode"), "vector");
    expect(screen.getByLabelText("use_random")).toBeInTheDocument();
  });

  it("submits both actions through createGenerationJob and tracks the returned job", async () => {
    renderPage();
    await screen.findByText("IndexTTS-2.5 / cuda");
    await userEvent.click(screen.getByRole("button", { name: "Quick preview" }));
    await waitFor(() => expect(apiClient.createGenerationJob).toHaveBeenCalledWith(expect.objectContaining({ model_id: "IndexTTS-2.5", params: expect.objectContaining({ take_count: 1 }) })));
    expect(screen.getByText(/job-1/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Generate multiple Takes" }));
    await waitFor(() => expect(apiClient.createGenerationJob).toHaveBeenLastCalledWith(expect.objectContaining({ params: expect.objectContaining({ take_count: 3 }) })));
  });

  it("inserts the documented language-specific pronunciation syntax", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /Pinyin annotation helper/i }));
    fireEvent.change(screen.getByLabelText("Source phrase"), { target: { value: "行" } });
    fireEvent.change(screen.getByLabelText("Pronunciation"), { target: { value: "XING2" } });
    await userEvent.click(screen.getByRole("button", { name: "Insert annotation" }));
    expect((screen.getByLabelText("targetText") as HTMLTextAreaElement).value).toContain("<行|XING2>");
  });

  it("blocks invalid duration and empty or unavailable text emotion before submit", async () => {
    renderPage();
    await screen.findByText("IndexTTS-2.5 / cuda");
    fireEvent.change(screen.getByLabelText("Duration factor"), { target: { value: "0.4" } });
    expect(screen.getByRole("button", { name: "Generate multiple Takes" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Duration factor"), { target: { value: "1" } });
    await userEvent.selectOptions(screen.getByLabelText("emotionMode"), "text_prompt");
    expect(screen.getByRole("button", { name: "Generate multiple Takes" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("emotionText"), "tense");
    expect(screen.getByRole("button", { name: "Generate multiple Takes" })).toBeEnabled();

    vi.mocked(apiClient.getRuntimeBackends).mockResolvedValue({ items: [{ ...runtime, text_emotion_enabled: false }] });
    await userEvent.click(screen.getByRole("button", { name: "retry" }));
    await waitFor(() => expect(screen.getByLabelText("emotionMode")).toHaveValue("same_voice"));
    expect(screen.queryByLabelText("emotionText")).not.toBeInTheDocument();
  });
});
