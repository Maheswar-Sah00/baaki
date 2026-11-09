// Count-up engine for the Baaki Meter: animate a number through a queue of targets with easing and
// a short hold at each step. Framework-free; the hook wires its callbacks to React state.

import { easeOutCubic, prefersReducedMotion } from "./easing";

export type CounterCallbacks = {
  onFrame: (value: number) => void;
  onStep: (value: number, index: number) => void;
  onIdle: () => void;
  onBusy: () => void;
};

export function createCounter(cb: CounterCallbacks, opts: { holdMs?: number } = {}) {
  const holdMs = opts.holdMs ?? 140;
  let value = 0;
  let queue: number[] = [];
  let raf: number | null = null;
  let hold: number | null = null;
  let stepIndex = 0;

  const segmentMs = (delta: number) => Math.max(420, Math.min(950, 380 + Math.abs(delta) / 25));

  const cancel = () => {
    if (raf !== null) cancelAnimationFrame(raf);
    if (hold !== null) window.clearTimeout(hold);
    raf = null;
    hold = null;
  };

  const set = (v: number) => {
    value = v;
    cb.onFrame(v);
  };

  const next = () => {
    cancel();
    const target = queue.shift();
    if (target === undefined) {
      cb.onIdle();
      return;
    }
    cb.onBusy();
    if (prefersReducedMotion()) {
      queue = [];
      set(target);
      cb.onStep(target, stepIndex++);
      cb.onIdle();
      return;
    }
    const from = value;
    const dur = segmentMs(target - from);
    let t0: number | null = null;
    const frame = (now: number) => {
      if (t0 === null) t0 = now;
      const p = Math.min(1, (now - t0) / dur);
      set(from + (target - from) * easeOutCubic(p));
      if (p < 1) {
        raf = requestAnimationFrame(frame);
      } else {
        raf = null;
        set(target);
        cb.onStep(target, stepIndex++);
        hold = window.setTimeout(next, queue.length ? holdMs : 0);
      }
    };
    raf = requestAnimationFrame(frame);
  };

  return {
    get value() {
      return value;
    },
    /** Animate from the current value through the steps still ahead, ending exactly on `total`. */
    animateTo(steps: number[], total: number) {
      let targets: number[];
      if (total >= value) {
        targets = steps.filter((s) => s > value + 0.5 && s <= total);
        if (targets.length === 0 || targets[targets.length - 1] !== total) targets.push(total);
      } else {
        targets = [total];
      }
      if (targets.length === 1 && Math.abs(targets[0] - value) < 0.5 && raf === null && hold === null) return;
      queue = targets;
      next();
    },
    /** Jump without animation. */
    jump(v: number) {
      cancel();
      queue = [];
      set(v);
      cb.onIdle();
    },
    dispose: cancel,
  };
}
