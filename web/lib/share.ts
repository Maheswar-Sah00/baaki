// Sharing a ladder step: Web Share with the voice-note file + text + employer link, then a WhatsApp
// URL, then the clipboard. The worker presses Send herself every time.

export type ShareResult = "shared" | "shared_text" | "whatsapp" | "copied" | "cancelled" | "failed";

/** Fetch an audio URL into a File that Web Share accepts (clean MIME, no codecs parameter). */
export async function fileFromUrl(url: string, name: string, signal?: AbortSignal): Promise<File> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`audio ${res.status}`);
  const raw = await res.blob();
  const ext = name.split(".").pop()?.toLowerCase();
  const type =
    ext === "ogg" || ext === "opus" ? "audio/ogg" : ext === "mp3" ? "audio/mpeg" : ext === "pdf" ? "application/pdf" : raw.type;
  return new File([raw], name, { type });
}

export function whatsappUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

function isAbortError(err: unknown) {
  return err instanceof DOMException && err.name === "AbortError";
}

/**
 * Share text + link (+ an optional prepared audio File). Call from a click handler: Web Share needs
 * a user gesture, so prepare the File beforehand (useMessages does this when the step is generated).
 */
export async function shareMessage(opts: {
  text: string;
  url?: string;
  title?: string;
  file?: File | null;
}): Promise<ShareResult> {
  const fullText = opts.url ? `${opts.text}\n\n${opts.url}` : opts.text;
  const nav = typeof navigator !== "undefined" ? navigator : null;
  if (nav?.share) {
    if (opts.file && nav.canShare?.({ files: [opts.file] })) {
      try {
        await nav.share({ files: [opts.file], text: fullText, title: opts.title });
        return "shared";
      } catch (err) {
        if (isAbortError(err)) return "cancelled";
        // fall through to a text-only share
      }
    }
    try {
      await nav.share({ text: opts.text, url: opts.url, title: opts.title });
      return "shared_text";
    } catch (err) {
      if (isAbortError(err)) return "cancelled";
    }
  }
  try {
    const w = window.open(whatsappUrl(fullText), "_blank", "noopener,noreferrer");
    if (w !== null) return "whatsapp";
  } catch {
    /* popup blocked */
  }
  return (await copyText(fullText)) ? "copied" : "failed";
}

/** A rough "is this a phone" check, used to pick the UPI deep link vs. the QR code. */
export function isLikelyMobile(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  if (/Android|iPhone|iPad|iPod|Mobile/i.test(ua)) return true;
  return typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches === true;
}
