import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const STORAGE_KEY = "darkMode";

function applyTheme(isDark) {
  document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
  if (isDark) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

export default function DarkModeIconButton() {
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === "undefined") return false;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved !== null) return saved === "true";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    applyTheme(darkMode);
  }, [darkMode]);

  const toggle = () => {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
      title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
      data-testid="dark-mode-toggle-button"
      className="fixed bottom-6 right-6 z-[60] w-12 h-12 rounded-full flex items-center justify-center bg-[#1A1A1A] text-white shadow-[0_8px_24px_rgba(0,0,0,0.25)] hover:scale-105 active:scale-95 transition"
    >
      {darkMode ? (
        <Sun className="w-5 h-5 text-yellow-300" />
      ) : (
        <Moon className="w-5 h-5 text-white" />
      )}
    </button>
  );
}
