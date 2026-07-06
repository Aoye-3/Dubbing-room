import { useState } from "react";
import { Languages, PanelLeftClose, PanelLeftOpen, Sparkles } from "lucide-react";
import { navItems } from "./navigation";
import type { LanguageCode, PageKey, ShellStatus } from "../shared/types";
import type { MessageKey } from "./i18n";

type AppShellProps = {
  activePage: PageKey;
  language: LanguageCode;
  status: ShellStatus;
  setActivePage: (page: PageKey) => void;
  setLanguage: (language: LanguageCode) => void;
  t: (key: MessageKey) => string;
  children: React.ReactNode;
};

export function AppShell({ activePage, language, status, setActivePage, setLanguage, t, children }: AppShellProps) {
  const [isRailExpanded, setIsRailExpanded] = useState(true);
  const activeNav = navItems.find((item) => item.key === activePage);
  const railToggleLabel = isRailExpanded ? t("collapseMenu") : t("expandMenu");
  const RailToggleIcon = isRailExpanded ? PanelLeftClose : PanelLeftOpen;

  return (
    <div className={`app-shell ${isRailExpanded ? "rail-expanded" : "rail-collapsed"}`}>
      <aside className="rail" aria-label="Primary">
        <div className="rail-header">
          <div className="brand-mark">
            <Sparkles size={24} strokeWidth={2.1} />
          </div>
          <button
            className="rail-toggle"
            type="button"
            title={railToggleLabel}
            aria-label={railToggleLabel}
            onClick={() => setIsRailExpanded((value) => !value)}
          >
            <RailToggleIcon size={20} strokeWidth={2.05} />
          </button>
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
                <span>{label}</span>
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
        {children}
      </main>
    </div>
  );
}

export function LanguageSwitch({
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
