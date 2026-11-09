"use client";

import { useEffect, useRef, useState } from "react";
import { easeOutCubic, prefersReducedMotion } from "@/lib/easing";

/** Animates from the last shown value to `target` (eased). Reduced motion: jumps. */
export function useCountTo(target: number | null, durationMs = 950): number {
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (target === null) return;
    if (raf.current !== null) cancelAnimationFrame(raf.current);
    if (prefersReducedMotion()) {
      raf.current = requestAnimationFrame(() => {
        from.current = target;
        setShown(target);
      });
      return;
    }
    const start = from.current;
    let t0: number | null = null;
    const step = (now: number) => {
      if (t0 === null) t0 = now;
      const p = Math.min(1, (now - t0) / durationMs);
      const v = start + (target - start) * easeOutCubic(p);
      from.current = v;
      setShown(v);
      if (p < 1) raf.current = requestAnimationFrame(step);
      else raf.current = null;
    };
    raf.current = requestAnimationFrame(step);
    // Safety net: if frames stall (background tab, capture tools), still land on the exact value.
    const done = window.setTimeout(() => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
      raf.current = null;
      from.current = target;
      setShown(target);
    }, durationMs + 400);
    return () => {
      window.clearTimeout(done);
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [target, durationMs]);

  return shown;
}
