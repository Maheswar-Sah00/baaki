// The PWA share target (add-on, registered in public/manifest.webmanifest): the service worker puts the
// shared voice note in Cache Storage under SHARE_KEY and opens /inbox/share. These helpers read and clear it.

export const SHARE_CACHE = "baaki-share-v1";
export const SHARE_KEY = "/__baaki_shared/file";

export async function readSharedFile(): Promise<File | null> {
  try {
    if (typeof caches === "undefined") return null;
    const cache = await caches.open(SHARE_CACHE);
    const res = await cache.match(SHARE_KEY);
    if (!res) return null;
    const blob = await res.blob();
    const name = decodeURIComponent(res.headers.get("x-filename") || "whatsapp-voice-note.ogg");
    const text = res.headers.get("x-shared-text");
    if (!blob.size && text) return new File([decodeURIComponent(text)], "shared.txt", { type: "text/plain" });
    return new File([blob], name, { type: blob.type || "audio/ogg" });
  } catch {
    return null;
  }
}

export async function clearSharedFile(): Promise<void> {
  try {
    if (typeof caches !== "undefined") await (await caches.open(SHARE_CACHE)).delete(SHARE_KEY);
  } catch {
    /* nothing to clear */
  }
}
