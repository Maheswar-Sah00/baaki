"use client";

// The step-up plan as a calm stepped bar chart: pale bars (now = paper, steps = sky, the last step = sage), the
// amount in ink above each bar, the month under it, and a dashed line at the legal estimate when it is shown.
// Purely presentational; the numbers come from the raise view. Bars grow in on mount (off with reduced motion).

import type { CSSProperties } from "react";
import { rupees } from "@/lib/features/raise";
import css from "./raise.module.css";

export type Step = { label: string; amount: number };

export function StepChart({
  steps,
  legal,
  legalLabel,
  className,
}: {
  steps: Step[];
  legal?: number | null;
  legalLabel?: string;
  className?: string;
}) {
  if (!steps.length) return null;
  const max = Math.max(...steps.map((s) => s.amount), legal ?? 0, 1);
  // Start the axis a little under the smallest bar so the steps read clearly (never at 0 for tiny gaps).
  const min = Math.max(0, Math.min(...steps.map((s) => s.amount)) * 0.55);
  const pct = (v: number) => Math.max(12, ((v - min) / (max - min || 1)) * 100);
  return (
    <figure
      className={`${css.chart} ${className ?? ""}`}
      aria-label={steps.map((s) => `${s.label}: ${rupees(s.amount)}`).join(", ")}
    >
      <div className={css.chartPlot} style={{ "--cols": steps.length } as CSSProperties}>
        {legal ? (
          <div className={css.chartArea} aria-hidden="true">
            <div className={css.chartLegal} style={{ bottom: `${pct(legal)}%` }}>
              {legalLabel ? <span>{legalLabel}</span> : null}
            </div>
          </div>
        ) : null}
        {steps.map((s, i) => (
          <div key={`${s.label}-${i}`} className={css.chartCol} aria-hidden="true">
            <span
              className={css.chartBar}
              data-step={i === 0 ? "now" : i === steps.length - 1 ? "last" : "mid"}
              style={{ height: `${pct(s.amount)}%`, animationDelay: `${i * 160}ms` }}
            >
              <span className={css.chartValue} style={{ animationDelay: `${300 + i * 160}ms` }}>
                {rupees(s.amount)}
              </span>
            </span>
          </div>
        ))}
      </div>
      <div className={css.chartLabels} style={{ "--cols": steps.length } as CSSProperties} aria-hidden="true">
        {steps.map((s, i) => (
          <span key={`l-${i}`}>{s.label}</span>
        ))}
      </div>
    </figure>
  );
}
