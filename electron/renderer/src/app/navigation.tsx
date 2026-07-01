import {
  AudioWaveform,
  FileAudio,
  History,
  Library,
  Mic2,
  RefreshCw,
  Settings,
  SlidersHorizontal,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import type { PageKey } from "../shared/types";
import type { MessageKey } from "./i18n";

type NavItem = {
  key: PageKey;
  labelKey: MessageKey;
  icon: import("react").ComponentType<{ size?: number; strokeWidth?: number }>;
};
export const navItems: NavItem[] = [
  { key: "design", labelKey: "navDesign", icon: WandSparkles },
  { key: "clone", labelKey: "navClone", icon: Mic2 },
  { key: "ultimate", labelKey: "navUltimate", icon: AudioWaveform },
  { key: "indexTTS2", labelKey: "navIndexTTS2", icon: Sparkles },
  { key: "loraTraining", labelKey: "navLoraTraining", icon: SlidersHorizontal },
  { key: "loraInference", labelKey: "navLoraInference", icon: FileAudio },
  { key: "library", labelKey: "navLibrary", icon: Library },
  { key: "history", labelKey: "navHistory", icon: History },
  { key: "jobs", labelKey: "navJobs", icon: RefreshCw },
  { key: "settings", labelKey: "navSettings", icon: Settings },
];
