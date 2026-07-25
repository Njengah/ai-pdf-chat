export type ThemeMode = "light" | "dark";

const KEY = "ai_pdf_chat_theme";

export function getTheme(): ThemeMode {
  const saved = localStorage.getItem(KEY);
  if (saved === "dark" || saved === "light") return saved;
  if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

export function applyTheme(theme: ThemeMode) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(KEY, theme);
}

export function initTheme() {
  applyTheme(getTheme());
}
