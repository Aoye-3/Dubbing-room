import { useCallback, useEffect, useState } from "react";
import type { MessageKey } from "../app/i18n";
import { apiClient } from "./api/client";
import type { AppGeneration } from "./types";

export function useGenerationAudioExport(record: AppGeneration | null, t: (key: MessageKey) => string) {
  const [exportMessage, setExportMessage] = useState("");
  const [exportError, setExportError] = useState("");
  const audioPath = record?.output_audio_path ?? "";

  useEffect(() => {
    setExportMessage("");
    setExportError("");
  }, [audioPath, record?.id]);

  const exportAudio = useCallback(async () => {
    if (!audioPath) {
      return;
    }
    setExportMessage("");
    setExportError("");
    try {
      const result = await apiClient.exportAudioFile({
        project_relative_path: audioPath,
        suggested_name: `${record?.id ?? "generation"}.wav`,
      });
      if (result.ok) {
        setExportMessage(t("exportSuccess"));
      }
    } catch (exportFailure) {
      setExportError(exportFailure instanceof Error ? exportFailure.message : String(exportFailure));
    }
  }, [audioPath, record?.id, t]);

  return {
    canExport: Boolean(audioPath),
    exportAudio,
    exportMessage,
    exportError,
  };
}
