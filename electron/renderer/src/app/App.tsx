import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../shared/api/client";
import type { AppDataState, AppGeneration, AppVoice, LanguageCode, PageKey, ShellState, ShellStatus } from "../shared/types";
import { AppShell } from "./AppShell";
import { messages, type MessageKey } from "./i18n";
import { AppRoutes } from "./routes";

export function App() {
  const [activePage, setActivePage] = useState<PageKey>("design");
  const [language, setLanguage] = useState<LanguageCode>(() => {
    const saved = window.localStorage.getItem("voxcpm-app-language");
    return saved === "zh" || saved === "en" ? saved : "zh";
  });
  const [shellState, setShellState] = useState<ShellState | null>(null);
  const [status, setStatus] = useState<ShellStatus>({
    state: "starting",
    message: messages.zh.starting,
    detail: "",
  });
  const [voices, setVoices] = useState<AppVoice[]>([]);
  const [generations, setGenerations] = useState<AppGeneration[]>([]);
  const [appDataState, setAppDataState] = useState<AppDataState>("idle");
  const [appDataError, setAppDataError] = useState("");

  const t = useMemo(() => {
    return (key: MessageKey) => messages[language][key] ?? messages.en[key];
  }, [language]);

  useEffect(() => {
    window.localStorage.setItem("voxcpm-app-language", language);
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  }, [language]);

  useEffect(() => {
    apiClient.getShellState().then((state) => {
      if (!state) {
        return;
      }
      setShellState(state);
      setStatus(state.status);
    });
    apiClient.onStatus((payload) => setStatus(payload));
  }, []);

  const loadAppData = useCallback(async () => {
    setAppDataState("loading");
    setAppDataError("");
    try {
      const [voiceResult, generationResult] = await Promise.all([
        apiClient.listVoices(),
        apiClient.listGenerations(),
      ]);
      setVoices(voiceResult.items);
      setGenerations(generationResult.items);
      setAppDataState("ready");
    } catch (error) {
      setAppDataState("failed");
      setAppDataError(error instanceof Error ? error.message : String(error));
    }
  }, []);

  const appReady = status.state === "ready";

  useEffect(() => {
    if (appReady) {
      loadAppData();
    }
  }, [appReady, loadAppData]);

  return (
    <AppShell
      activePage={activePage}
      language={language}
      status={status}
      setActivePage={setActivePage}
      setLanguage={setLanguage}
      t={t}
    >
      <AppRoutes
        activePage={activePage}
        appReady={appReady}
        status={status}
        voices={voices}
        generations={generations}
        appDataState={appDataState}
        appDataError={appDataError}
        shellState={shellState}
        language={language}
        setLanguage={setLanguage}
        reload={loadAppData}
        t={t}
      />
    </AppShell>
  );
}
