"use client";

// Text that types itself out, holds, and starts again (a live transcript look). Reduced motion: full text.

import { useEffect, useState } from "react";
import { prefersReducedMotion } from "@/lib/easing";

export function TypeLoop({ text, lang, stepMs = 70, holdMs = 2600, className }: { text: string; lang?: string; stepMs?: number; holdMs?: number; className?: string }) {
  const chars = Array.from(text);
  const [n, setN] = useState(chars.length);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let i = 0;
    let timer = 0;
    const tick = () => {
      i += 1;
      setN(Math.min(i, chars.length));
      timer = window.setTimeout(tick, i >= chars.length ? holdMs : stepMs);
      if (i > chars.length) i = 0;
    };
    timer = window.setTimeout(tick, 400);
    return () => window.clearTimeout(timer);
  }, [chars.length, stepMs, holdMs]);
  return (
    <span className={className} lang={lang}>
      {chars.slice(0, n).join("")}
      <span className="s-caret" aria-hidden="true" />
    </span>
  );
}
