"use client";

// "Install app" button for the PWA. Chrome/Edge/Android: uses the beforeinstallprompt event that
// the pre-paint script in app/layout.tsx stashes on window.__baakiInstall. iPhone Safari (no
// prompt API): shows the Share -> Add to Home Screen hint. Hidden when already installed.

import { useEffect, useState, useSyncExternalStore } from "react";
import { DownloadIcon } from "./icons";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type WinWithInstall = Window & { __baakiInstall?: InstallEvent | null };

function subscribe(cb: () => void) {
  window.addEventListener("baaki:installable", cb);
  return () => window.removeEventListener("baaki:installable", cb);
}
const getEvent = () => (window as WinWithInstall).__baakiInstall ?? null;

function detectMode(): "standalone" | "ios" | "other" {
  const standalone =
    window.matchMedia?.("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (standalone) return "standalone";
  const ua = navigator.userAgent;
  const ios = /iphone|ipad|ipod/i.test(ua) || (ua.includes("Mac") && "ontouchend" in document);
  return ios ? "ios" : "other";
}

export function InstallButton({
  label = "Install app",
  iosHint = "On iPhone: tap Share, then “Add to Home Screen”.",
  variant = "pill",
  className,
}: {
  label?: string;
  iosHint?: string;
  variant?: "pill" | "block" | "ghost";
  className?: string;
}) {
  const event = useSyncExternalStore(subscribe, getEvent, () => null);
  const [mode, setMode] = useState<"standalone" | "ios" | "other" | null>(null);
  const [hint, setHint] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMode(detectMode()));
    return () => cancelAnimationFrame(id);
  }, []);

  if (mode === null || mode === "standalone") return null;
  if (!event && mode !== "ios") return null;

  return (
    <span className={`install ${className ?? ""}`}>
      <button
        type="button"
        className={`btn install-btn install-${variant}`}
        onClick={async () => {
          if (event) {
            await event.prompt();
            try {
              await event.userChoice;
            } finally {
              (window as WinWithInstall).__baakiInstall = null;
              window.dispatchEvent(new Event("baaki:installable"));
            }
          } else {
            setHint((h) => !h);
          }
        }}
        aria-expanded={mode === "ios" ? hint : undefined}
      >
        <DownloadIcon />
        <span>{label}</span>
      </button>
      {hint ? (
        <span className="install-hint" role="status">
          {iosHint}
        </span>
      ) : null}
    </span>
  );
}
