"use client";

// Always-visible "install" control for the website (the shared <InstallButton> hides itself when the
// browser has not offered an install prompt). Uses the same stashed beforeinstallprompt event
// (window.__baakiInstall, see lib/theme-config.ts); otherwise shows how to add Baaki to the home
// screen. Already installed: opens the app instead.

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { DownloadIcon } from "@/components/ui/icons";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type WinWithInstall = Window & { __baakiInstall?: InstallEvent | null };

function subscribe(cb: () => void) {
  window.addEventListener("baaki:installable", cb);
  return () => window.removeEventListener("baaki:installable", cb);
}
const getEvent = () => (window as WinWithInstall).__baakiInstall ?? null;

export function InstallCta({ label, variant = "pill", className }: { label: string; variant?: "pill" | "link"; className?: string }) {
  const event = useSyncExternalStore(subscribe, getEvent, () => null);
  const [mode, setMode] = useState<"standalone" | "ios" | "other">("other");
  const [hint, setHint] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      const standalone =
        window.matchMedia?.("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
      const ua = navigator.userAgent;
      const ios = /iphone|ipad|ipod/i.test(ua) || (ua.includes("Mac") && "ontouchend" in document);
      setMode(standalone ? "standalone" : ios ? "ios" : "other");
    });
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    if (!hint) return;
    const t = window.setTimeout(() => setHint(false), 6000);
    return () => window.clearTimeout(t);
  }, [hint]);

  const cls = variant === "pill" ? `s-pill s-pill-white ${className ?? ""}` : `s-textlink ${className ?? ""}`;

  if (mode === "standalone") {
    return (
      <Link href="/app" className={cls}>
        {variant === "pill" ? <DownloadIcon /> : null}
        <span>Open Baaki</span>
      </Link>
    );
  }

  return (
    <span className="s-install-wrap">
      <button
        type="button"
        className={cls}
        aria-expanded={event ? undefined : hint}
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
      >
        {variant === "pill" ? <DownloadIcon /> : null}
        <span>{label}</span>
      </button>
      {hint ? (
        <span className="s-install-hint" role="status">
          {mode === "ios"
            ? "On iPhone: tap Share, then “Add to Home Screen”."
            : "On your phone, open this page in Chrome, tap ⋮, then “Install app” or “Add to Home screen”."}
        </span>
      ) : null}
    </span>
  );
}
