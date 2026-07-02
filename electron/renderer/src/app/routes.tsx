import { SlidersHorizontal } from "lucide-react";
import { JobListPage } from "../jobs/JobListPage";
import { IndexTTS2Page } from "../indextts2/IndexTTS2Page";
import { HistoryPage } from "../storage/HistoryPage";
import { VoiceLibraryPage } from "../storage/VoiceLibraryPage";
import { VoxCPMPage } from "../voxcpm/VoxCPMPage";
import type { AppDataState, AppGeneration, AppVoice, FeatureMode, LanguageCode, PageKey, ShellState, ShellStatus } from "../shared/types";
import type { MessageKey } from "./i18n";
import { LanguageSwitch } from "./AppShell";

type AppRoutesProps = {
  activePage: PageKey;
  appReady: boolean;
  status: ShellStatus;
  voices: AppVoice[];
  generations: AppGeneration[];
  appDataState: AppDataState;
  appDataError: string;
  shellState: ShellState | null;
  language: LanguageCode;
  setLanguage: (language: LanguageCode) => void;
  reload: () => Promise<void>;
  t: (key: MessageKey) => string;
};

export function AppRoutes({
  activePage,
  appReady,
  status,
  voices,
  generations,
  appDataState,
  appDataError,
  shellState,
  language,
  setLanguage,
  reload,
  t,
}: AppRoutesProps) {
  if (activePage === "design") {
    return <VoxCPMPage mode={t("navDesign")} status={status} appReady={appReady} accent="design" modeKey="voice-design" description={t("designDescription")} voices={voices} reload={reload} t={t} />;
  }
  if (activePage === "clone") {
    return <VoxCPMPage mode={t("navClone")} status={status} appReady={appReady} accent="clone" modeKey="voice-cloning" description={t("cloneDescription")} voices={voices} reload={reload} t={t} />;
  }
  if (activePage === "ultimate") {
    return <VoxCPMPage mode={t("navUltimate")} status={status} appReady={appReady} accent="ultimate" modeKey="ultimate-cloning" description={t("ultimateDescription")} voices={voices} reload={reload} t={t} />;
  }
  if (activePage === "indexTTS2") {
    return <IndexTTS2Page appReady={appReady} status={status} voices={voices} reload={reload} t={t} />;
  }
  if (activePage === "loraTraining") {
    return <ReservedFeaturePage mode={t("navLoraTraining")} modeKey="lora-training" description={t("loraTrainingDescription")} t={t} />;
  }
  if (activePage === "loraInference") {
    return <ReservedFeaturePage mode={t("navLoraInference")} modeKey="lora-inference" description={t("loraInferenceDescription")} t={t} />;
  }
  if (activePage === "library") {
    return <VoiceLibraryPage voices={voices} appDataState={appDataState} appDataError={appDataError} reload={reload} t={t} />;
  }
  if (activePage === "history") {
    return <HistoryPage generations={generations} appDataState={appDataState} appDataError={appDataError} reload={reload} t={t} />;
  }
  if (activePage === "jobs") {
    return <JobListPage labels={{ jobs: t("navJobs"), retry: t("retry"), cancel: t("cancel"), noJobs: t("noJobs"), takes: t("takes") }} />;
  }
  return <SettingsPage status={status} shellState={shellState} language={language} setLanguage={setLanguage} t={t} />;
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
          <dd>{shellState?.mainPort ?? "--"}</dd>
          <dt>{t("appBackend")}</dt>
          <dd>{shellState?.appBackendUrl ?? "--"}</dd>
          <dt>{t("legacyBackend")}</dt>
          <dd>{shellState?.legacyBackendUrl ?? "--"}</dd>
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
          <dd>{shellState?.projectDir ?? "--"}</dd>
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