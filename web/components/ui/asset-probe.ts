"use client";

// Probe for static images that may not exist yet (/assets/*.webp the user supplies later).
// One shared, per-tab memory of which files loaded and which 404'd, so a missing file is requested
// once: later mounts (client navigations) render the fallback straight away, with no flash.
//
// A server-rendered <img> can fail (or load) before React hydrates, so onError/onLoad never fire;
// the callback ref runs when the element is attached (after hydration too) and reads `complete` +
// `naturalWidth` to catch that case. During hydration useSyncExternalStore uses the server snapshot
// (unknown), so the markup always matches the server render; the client snapshot applies right after.

import { useCallback, useSyncExternalStore } from "react";

export type AssetStatus = "ok" | "missing";

const known = new Map<string, AssetStatus>();
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function markAsset(src: string, status: AssetStatus) {
  if (known.get(src) === status) return;
  known.set(src, status);
  listeners.forEach((l) => l());
}

/**
 * Status of one image URL: "ok" (loaded), "missing" (404 / broken) or undefined (not known yet:
 * render the <img> with the returned `ref`, `onLoad` and `onError`; it reports back).
 */
export function useAssetStatus(src: string | null | undefined) {
  const getSnapshot = useCallback(() => (src ? known.get(src) : "missing"), [src]);
  const getServerSnapshot = useCallback(() => (src ? undefined : "missing"), [src]);
  const status = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot) as AssetStatus | undefined;

  const ref = useCallback(
    (img: HTMLImageElement | null) => {
      if (!img || !src || !img.complete) return;
      markAsset(src, img.naturalWidth > 0 ? "ok" : "missing");
    },
    [src],
  );
  const onLoad = useCallback(() => {
    if (src) markAsset(src, "ok");
  }, [src]);
  const onError = useCallback(() => {
    if (src) markAsset(src, "missing");
  }, [src]);

  return { status, ref, onLoad, onError };
}
