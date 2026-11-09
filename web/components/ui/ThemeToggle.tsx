"use client";

// Light / dark switch. The new theme grows as a circle from this button across the whole page
// (lib/theme.ts switchTheme, View Transitions API); instant switch where unsupported or with
// reduced motion. Works on the website and in the app.

import { switchTheme, useTheme } from "@/lib/theme";
import { useHydrated } from "@/hooks/useSettings";
import { MoonIcon, SunIcon } from "./icons";

export function ThemeToggle({ className, labels }: { className?: string; labels?: { toLight: string; toDark: string } }) {
  const theme = useTheme();
  const hydrated = useHydrated();
  const dark = hydrated && theme === "dark";
  const label = dark ? labels?.toLight ?? "Switch to light theme" : labels?.toDark ?? "Switch to dark theme";
  return (
    <button
      type="button"
      className={`icon-btn theme-toggle ${className ?? ""}`}
      data-dark={dark}
      aria-label={label}
      title={label}
      onClick={(e) => {
        const b = e.currentTarget.getBoundingClientRect();
        switchTheme(dark ? "light" : "dark", b.left + b.width / 2, b.top + b.height / 2);
      }}
    >
      <SunIcon className="theme-toggle-sun" />
      <MoonIcon className="theme-toggle-moon" />
    </button>
  );
}
