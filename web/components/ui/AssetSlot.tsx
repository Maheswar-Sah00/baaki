"use client";

// A place for a real image the user will supply later (prompts in docs/ASSET_PROMPTS.md).
// Renders /assets/<name>.webp (or .png/.jpg via `ext`) when the file exists; until then a calm pale
// placeholder in the same shape (a faint dotted grid on the slot's wash, plus optional `fallback`
// art in the middle), so layouts never jump and nothing looks broken. Placeholders never show text:
// no file names reach users (the slot name is on `data-slot` for developers).
//   <AssetSlot name="hero-lakshmi-kitchen" ratio="4/5" alt="Lakshmi in a Hyderabad kitchen" tone="peach" />
//   <AssetSlot name="inbox-empty" ratio="4/3" alt="" tone="sage" fit="contain" fallback={<Illustration name="wave" />} />
// Optional `darkName` swaps in a dark-theme variant (/assets/<darkName>.webp) under [data-theme=dark].
// `fit="contain"` centres a transparent illustration (flat cartoon WebP) on the slot's pale tone
// (light) / dark tone (dark) instead of cropping it like a photo, with breathing room around it.
// `anchor="bottom"` is for art with a cut ("bleed") bottom edge: it sits flush on the slot's bottom
// edge (object-position: center bottom, no padding below) so a figure rises out of the card edge.
// `anchor="right"` pins wide banners whose art lives on the right (the left stays calm and empty).
//
// Missing-file detection is shared with <Illustration> (components/ui/asset-probe.ts): onError plus
// a mount-time `complete && naturalWidth === 0` check, remembered per tab.

import type { ReactNode } from "react";
import { useAssetStatus } from "./asset-probe";

type Tone = "sky" | "lilac" | "peach" | "butter" | "sage" | "rose";

export function AssetSlot({
  name,
  darkName,
  alt,
  ratio = "16/10",
  tone = "sky",
  ext = "webp",
  className,
  rounded = "var(--r-xl)",
  label,
  priority,
  fit = "cover",
  anchor = "center",
  fallback,
}: {
  name: string;
  darkName?: string;
  alt: string;
  ratio?: string;
  tone?: Tone;
  ext?: "webp" | "png" | "jpg";
  className?: string;
  rounded?: string;
  /** Kept for API compatibility. Placeholders no longer show any caption (never a file name). */
  label?: string;
  priority?: boolean;
  /** "cover" crops like a photo (default); "contain" centres a transparent illustration on the tone. */
  fit?: "cover" | "contain";
  /** Where the image sits: "center" (default), "bottom" (bleed art flush on the bottom edge), "right". */
  anchor?: "center" | "bottom" | "right";
  /** Art shown in the middle of the placeholder while the image is missing (an icon or <Illustration>). */
  fallback?: ReactNode;
}) {
  void label;
  const src = `/assets/${name}.${ext}`;
  const darkSrc = darkName ? `/assets/${darkName}.${ext}` : null;
  const { status: lightStatus, ref: lightRef, onLoad: lightLoad, onError: lightError } = useAssetStatus(src);
  const { status: darkStatus, ref: darkRef, onLoad: darkLoad, onError: darkError } = useAssetStatus(darkSrc);
  const missing = lightStatus === "missing";
  const darkMissing = !darkName || darkStatus === "missing";

  return (
    <div
      className={`asset-slot ${className ?? ""}`}
      data-missing={missing}
      data-loaded={lightStatus === "ok"}
      data-tone={tone}
      data-fit={fit}
      data-anchor={anchor}
      data-slot={name}
      style={{ aspectRatio: ratio, borderRadius: rounded }}
    >
      {!missing && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={lightRef}
          src={src}
          alt={alt}
          loading={priority ? "eager" : "lazy"}
          decoding="async"
          className={darkName && !darkMissing ? "asset-slot-light" : undefined}
          onLoad={lightLoad}
          onError={lightError}
        />
      )}
      {darkSrc && !darkMissing && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={darkRef}
          src={darkSrc}
          alt={alt}
          loading="lazy"
          decoding="async"
          className="asset-slot-dark"
          onLoad={darkLoad}
          onError={darkError}
        />
      )}
      {missing && (
        <div className="asset-slot-ph" role={alt ? "img" : undefined} aria-label={alt || undefined} aria-hidden={alt ? undefined : true}>
          {fallback ? <span className="asset-slot-art">{fallback}</span> : null}
        </div>
      )}
    </div>
  );
}
