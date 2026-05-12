import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const STORAGE_KEY = "darkMode";

function applyDarkMode(isDark) {
  if (isDark) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

export default function DarkModeIconButton({ className = "" }) {
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === "undefined") return false;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved !== null) return saved === "true";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    applyDarkMode(darkMode);
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
      className={`p-2.5 rounded-full hover:bg-white/10 transition ${className}`}
    >
      {darkMode ? (
        <Sun className="w-5 h-5 text-yellow-300" />
      ) : (
        <Moon className="w-5 h-5 text-white" />
      )}
    </button>
  );
}
