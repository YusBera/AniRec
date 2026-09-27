import { useSyncExternalStore } from "react";
import type { RecommendationViewModel } from "../api/types";

export type TitleLanguage = "english" | "original";
const STORAGE_KEY = "anirec.titleLanguage";
const listeners = new Set<() => void>();
let current: TitleLanguage = "english";

if (typeof window !== "undefined") {
  try { current = window.localStorage.getItem(STORAGE_KEY) === "original" ? "original" : "english"; }
  catch { current = "english"; }
  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) return;
    current = event.newValue === "original" ? "original" : "english";
    listeners.forEach((listener) => listener());
  });
}

export function useTitleLanguage(): TitleLanguage {
  return useSyncExternalStore(
    (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    () => current,
    () => "english",
  );
}

export function setTitleLanguage(value: TitleLanguage): void {
  current = value;
  try { window.localStorage.setItem(STORAGE_KEY, value); } catch { /* Preference still works for this session. */ }
  listeners.forEach((listener) => listener());
}

/** The API's secondary title is the original MAL title when English differs. */
export function preferredTitle(model: Pick<RecommendationViewModel, "display_title" | "secondary_title">, language: TitleLanguage): string {
  return language === "original" ? model.secondary_title?.trim() || model.display_title : model.display_title;
}
