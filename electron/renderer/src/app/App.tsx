import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AudioWaveform,
  Download,
  FileAudio,
  History,
  Languages,
  Library,
  Mic2,
  MoreHorizontal,
  Play,
  RefreshCw,
  Save,
  Settings,
  SlidersHorizontal,
  Sparkles,
  Star,
  Upload,
  WandSparkles,
} from "lucide-react";
import { JobListPage } from "../jobs/JobListPage";
import { apiClient } from "../shared/api/client";
import { messages, type MessageKey } from "./i18n";
import { navItems } from "./navigation";
import { mediaUrl } from "../shared/audio";
import { LoadingPanel } from "../shared/components";
import { VoxCPMPage } from "../voxcpm/VoxCPMPage";
import { HistoryPage } from "../storage/HistoryPage";
import { IndexTTS2Page } from "../indextts2/IndexTTS2Page";
import { VoiceLibraryPage } from "../storage/VoiceLibraryPage";
import type {
  AppDataState,
  AppGeneration,
  AppVoice,
  FeatureMode,
  GenerateAudioPayload,
  IndexTTS2EmotionMode,
  IndexTTS2Payload,
  LanguageCode,
  PageKey,
  ReferenceKind,
  RuntimeBackendStatus,
  SelectedAudioFile,
  ShellState,
  ShellStatus,
} from "../shared/types";

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

  useEffect(() => {
    loadAppData();
  }, [loadAppData]);

  const activeNav = useMemo(() => navItems.find((item) => item.key === activePage), [activePage]);
  const appReady = status.state === "ready";

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Primary">
        <div className="brand-mark">
          <Sparkles size={24} strokeWidth={2.1} />
        </div>
        <nav className="rail-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const label = t(item.labelKey);
            return (
              <button
                key={item.key}
                className={`rail-button ${activePage === item.key ? "active" : ""}`}
                title={label}
                aria-label={label}
                onClick={() => setActivePage(item.key)}
              >
                <Icon size={23} strokeWidth={2.05} />
              </button>
            );
          })}
        </nav>
        <div className="version">dev</div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{t("appTitle")}</p>
            <h1>{activeNav ? t(activeNav.labelKey) : ""}</h1>
          </div>
          <div className="topbar-actions">
            <LanguageSwitch language={language} setLanguage={setLanguage} />
            <BackendPill status={status} t={t} />
          </div>
        </header>

        {activePage === "design" && (
          <VoxCPMPage
            mode={t("navDesign")}
            status={status}
            appReady={appReady}
            accent="design"
            modeKey="voice-design"
            description={t("designDescription")}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "clone" && (
          <VoxCPMPage
            mode={t("navClone")}
            status={status}
            appReady={appReady}
            accent="clone"
            modeKey="voice-cloning"
            description={t("cloneDescription")}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "ultimate" && (
          <VoxCPMPage
            mode={t("navUltimate")}
            status={status}
            appReady={appReady}
            accent="ultimate"
            modeKey="ultimate-cloning"
            description={t("ultimateDescription")}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "indexTTS2" && (
          <IndexTTS2Page
            appReady={appReady}
            status={status}
            voices={voices}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "loraTraining" && (
          <ReservedFeaturePage
            mode={t("navLoraTraining")}
            modeKey="lora-training"
            description={t("loraTrainingDescription")}
            t={t}
          />
        )}
        {activePage === "loraInference" && (
          <ReservedFeaturePage
            mode={t("navLoraInference")}
            modeKey="lora-inference"
            description={t("loraInferenceDescription")}
            t={t}
          />
        )}
        {activePage === "library" && (
          <VoiceLibraryPage
            voices={voices}
            appDataState={appDataState}
            appDataError={appDataError}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "history" && (
          <HistoryPage
            generations={generations}
            appDataState={appDataState}
            appDataError={appDataError}
            reload={loadAppData}
            t={t}
          />
        )}
        {activePage === "jobs" && (
          <JobListPage
            labels={{
              jobs: t("navJobs"),
              retry: t("retry"),
              cancel: t("cancel"),
              noJobs: t("noJobs"),
              takes: t("takes"),
            }}
          />
        )}
        {activePage === "settings" && (
          <SettingsPage
            status={status}
            shellState={shellState}
            language={language}
            setLanguage={setLanguage}
            t={t}
          />
        )}
      </main>
    </div>
  );
}

function LanguageSwitch({
  language,
  setLanguage,
}: {
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
}) {
  return (
    <div className="language-switch" aria-label="Interface language">
      <Languages size={17} />
      <button className={language === "en" ? "active" : ""} type="button" onClick={() => setLanguage("en")}>
        EN
      </button>
      <button className={language === "zh" ? "active" : ""} type="button" onClick={() => setLanguage("zh")}>
        中
      </button>
    </div>
  );
}

function BackendPill({ status, t }: { status: ShellStatus; t: (key: MessageKey) => string }) {
  return (
    <div className={`backend-pill ${status.state}`}>
      <span />
      <strong>{status.state === "ready" ? t("appReady") : status.message}</strong>
    </div>
  );
}

function ReservedFeaturePage({
  mode,
  modeKey,
  description,
  t,
}: {
  mode: string;
  modeKey: FeatureMode;
  description: string;
  t: (key: MessageKey) => string;
}) {
  return (
    <section className="generation-grid reserved">
      <div className="mode-panel">
        <div className="mode-header">
          <SlidersHorizontal size={20} />
          <span>{mode}</span>
        </div>
        <p className="mode-description">{description}</p>
        <div className="field-stack">
          <label>
            <span>{t("pretrainedModel")}</span>
            <input value="openbmb/VoxCPM2" readOnly />
          </label>
          <label>
            <span>{modeKey === "lora-training" ? t("trainingManifest") : t("loraCheckpoint")}</span>
            <input value={modeKey === "lora-training" ? "examples/train_data_example.jsonl" : "None"} readOnly />
          </label>
          <label>
            <span>{t("outputDirectory")}</span>
            <input value={modeKey === "lora-training" ? "lora/" : "data/app/generations/"} readOnly />
          </label>
        </div>
      </div>
      <div className="native-workbench reserved-workbench">
        <div className="adapter-card">
          <h2>{mode}</h2>
          <p>{description}</p>
        </div>
      </div>
    </section>
  );
}

function SettingsPage({
  status,
  shellState,
  language,
  setLanguage,
  t,
}: {
  status: ShellStatus;
  shellState: ShellState | null;
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  t: (key: MessageKey) => string;
}) {
  return (
    <section className="settings-grid">
      <div className="settings-panel">
        <h2>{t("runtime")}</h2>
        <dl>
          <dt>{t("backend")}</dt>
          <dd>{status.state}</dd>
          <dt>{t("appMode")}</dt>
          <dd>{shellState?.appMode ?? "app-shell"}</dd>
          <dt>{t("port")}</dt>
          <dd>{shellState?.mainPort ?? 8818}</dd>
          <dt>{t("appBackend")}</dt>
          <dd>{shellState?.appBackendUrl ?? "http://127.0.0.1:8818"}</dd>
          <dt>{t("legacyBackend")}</dt>
          <dd>{shellState?.legacyBackendUrl ?? "http://127.0.0.1:8808"}</dd>
        </dl>
      </div>
      <div className="settings-panel">
        <h2>{t("interface")}</h2>
        <dl>
          <dt>{t("interfaceLanguage")}</dt>
          <dd>
            <LanguageSwitch language={language} setLanguage={setLanguage} />
          </dd>
          <dt>{t("language")}</dt>
          <dd>{language === "zh" ? t("chinese") : t("english")}</dd>
          <dt>{t("appMode")}</dt>
          <dd>{t("languageHint")}</dd>
        </dl>
      </div>
      <div className="settings-panel">
        <h2>{t("localPaths")}</h2>
        <dl>
          <dt>{t("project")}</dt>
          <dd>{shellState?.projectDir ?? "F:\\.VoxCPM\\VoxCPM"}</dd>
          <dt>{t("outputLog")}</dt>
          <dd>{shellState?.appBackendOutLogPath ?? "voxcpm_app_backend.out.log"}</dd>
          <dt>{t("errorLog")}</dt>
          <dd>{shellState?.appBackendErrLogPath ?? "voxcpm_app_backend.err.log"}</dd>
          <dt>{t("gradioRoute")}</dt>
          <dd>{t("gradioRouteValue")}</dd>
        </dl>
      </div>
    </section>
  );
}
