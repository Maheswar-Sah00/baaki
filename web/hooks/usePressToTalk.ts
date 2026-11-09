"use client";

// Tap OR hold on one mic button. Tap: starts, a second tap stops. Hold (>= holdMs): stops on release.
// Returns pointer handlers to spread on the button; works with mouse, touch and pen.

import { useCallback, useRef, type KeyboardEvent, type MouseEvent, type PointerEvent } from "react";
import type { RecorderState } from "@/lib/recorder";

export function usePressToTalk(
  rec: { state: RecorderState; start: () => Promise<void> | void; stop: () => void },
  opts: { holdMs?: number; disabled?: boolean } = {},
) {
  const holdMs = opts.holdMs ?? 500;
  const downAt = useRef<number | null>(null);
  const startedByThisPress = useRef(false);

  const onPointerDown = useCallback(
    (e: PointerEvent<HTMLElement>) => {
      if (opts.disabled || (e.pointerType === "mouse" && e.button !== 0)) return;
      if (rec.state === "recording") {
        // second tap in tap mode
        startedByThisPress.current = false;
        downAt.current = null;
        rec.stop();
        return;
      }
      if (rec.state !== "idle") return;
      downAt.current = performance.now();
      startedByThisPress.current = true;
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      void rec.start();
    },
    [rec, opts.disabled],
  );

  const onPointerUp = useCallback(() => {
    const t0 = downAt.current;
    downAt.current = null;
    if (!startedByThisPress.current || t0 === null) return;
    startedByThisPress.current = false;
    if (performance.now() - t0 >= holdMs) rec.stop(); // hold-to-talk released
    // a short tap keeps recording until the next tap
  }, [rec, holdMs]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLElement>) => {
      if (opts.disabled) return;
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        if (rec.state === "recording") rec.stop();
        else if (rec.state === "idle") void rec.start();
      }
    },
    [rec, opts.disabled],
  );

  return {
    onPointerDown,
    onPointerUp,
    onPointerCancel: onPointerUp,
    onKeyDown,
    onContextMenu: (e: MouseEvent) => e.preventDefault(),
  };
}
