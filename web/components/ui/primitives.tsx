"use client";

// Small presentational pieces shared by the screens. No data fetching here: props in, events out.
// Class names are plain and documented in app/globals.css so a design can restyle or replace them.

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { formatTimer } from "@/lib/recorder";
import { inr, inrWhole } from "@/lib/format";
import type { Translate } from "@/lib/i18n";
import type { MeterChip } from "@/lib/types";
import type { PlayerState } from "@/hooks/useAudioPlayer";
import { BackIcon, MicIcon, PauseIcon, PlayIcon, ShieldIcon, StopIcon } from "./icons";

// ------------------------------------------------------------------ layout
export function Screen({
  title,
  back,
  children,
  className,
  safetyLink = true,
  t,
}: {
  title?: ReactNode;
  back?: string;
  children: ReactNode;
  className?: string;
  safetyLink?: boolean;
  t?: Translate;
}) {
  return (
    <main className={`screen ${className ?? ""}`}>
      {title !== undefined || back || safetyLink ? (
        <header className="screen-head">
          {back ? (
            <Link href={back} className="icon-btn" aria-label={t ? t("common.back") : "Back"}>
              <BackIcon />
            </Link>
          ) : (
            <span className="icon-btn-spacer" />
          )}
          {title !== undefined ? <h1 className="screen-title">{title}</h1> : <span />}
          {safetyLink ? (
            <Link href="/safety" className="icon-btn" aria-label={t ? t("home.safety") : "Help"}>
              <ShieldIcon />
            </Link>
          ) : (
            <span className="icon-btn-spacer" />
          )}
        </header>
      ) : null}
      {children}
    </main>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <p className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" /> {label}
    </p>
  );
}

export function ErrorNote({ message, onRetry, retryLabel }: { message: string | null; onRetry?: () => void; retryLabel?: string }) {
  if (!message) return null;
  return (
    <div className="error-note" role="alert">
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          {retryLabel ?? "Try again"}
        </button>
      ) : null}
    </div>
  );
}

export function Money({ value, className }: { value: number; className?: string }) {
  return <span className={`money ${className ?? ""}`}>{inr(value)}</span>;
}

export function EstimateTag({ t }: { t: Translate }) {
  return <span className="tag tag-estimate">{t("common.estimate")}</span>;
}

// ------------------------------------------------------------------ mic
export function MicButton({
  state,
  level,
  elapsedMs,
  disabled,
  handlers,
  label,
  size = "big",
}: {
  state: "idle" | "starting" | "recording" | string;
  level: number;
  elapsedMs?: number;
  disabled?: boolean;
  handlers: Record<string, unknown>;
  label: string;
  size?: "big" | "small";
}) {
  const recording = state === "recording";
  return (
    <div className={`mic-wrap mic-${size}`}>
      <button
        type="button"
        className="mic"
        data-state={state}
        style={{ "--level": level } as CSSProperties}
        disabled={disabled}
        aria-label={label}
        aria-pressed={recording}
        {...handlers}
      >
        {recording ? <StopIcon /> : <MicIcon />}
      </button>
      <p className="mic-label" aria-live="polite">
        {recording && elapsedMs !== undefined ? `${formatTimer(elapsedMs)} · ${label}` : label}
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ Baaki Meter
export function MeterValue({ value, tick, animating, label }: { value: number; tick: number; animating: boolean; label: string }) {
  return (
    <div className="meter" data-animating={animating} data-tick={tick % 2}>
      <p className="meter-label">{label}</p>
      <p className="meter-value" aria-live="polite" aria-atomic="true">
        {inrWhole(value)}
      </p>
    </div>
  );
}

export function ChipView({
  chip,
  t,
  onRemove,
  onEdit,
  editing,
  setEditing,
}: {
  chip: MeterChip;
  t: Translate;
  onRemove: () => void;
  onEdit: (value: number) => void;
  editing: boolean;
  setEditing: (v: boolean) => void;
}) {
  const label = t(`chip.${chip.kind}` as Parameters<Translate>[0]);
  const shown = chip.is_count ? String(chip.value) : inr(chip.value);
  if (editing) {
    return (
      <form
        className="chip chip-editing"
        onSubmit={(e) => {
          e.preventDefault();
          const v = Number(new FormData(e.currentTarget).get("v"));
          if (Number.isFinite(v) && v >= 0) onEdit(v);
          setEditing(false);
        }}
      >
        <label>
          <span className="chip-label">{label}</span>
          <input name="v" type="number" inputMode="numeric" defaultValue={chip.value} autoFocus className="input chip-input" />
        </label>
        <button type="submit" className="btn btn-small">
          {t("speak.save")}
        </button>
        <button type="button" className="btn btn-small" onClick={onRemove}>
          {t("speak.remove")}
        </button>
      </form>
    );
  }
  return (
    <button type="button" className="chip" data-kind={chip.kind} onClick={() => setEditing(true)} title={chip.text}>
      <span className="chip-label">{label}</span>
      <span className="chip-value">{shown}</span>
    </button>
  );
}

// ------------------------------------------------------------------ audio
export function PlayButton({
  state,
  active,
  onClick,
  label,
  disabled,
  progress,
}: {
  state: PlayerState;
  active: boolean;
  onClick: () => void;
  label: string;
  disabled?: boolean;
  progress?: number;
}) {
  const playing = active && state === "playing";
  return (
    <button
      type="button"
      className="play-btn"
      data-state={active ? state : "idle"}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      style={{ "--progress": active ? progress ?? 0 : 0 } as CSSProperties}
    >
      {playing ? <PauseIcon /> : <PlayIcon />}
      <span>{label}</span>
    </button>
  );
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; disabled?: boolean }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" aria-hidden="true" />
      <span className="toggle-label">{label}</span>
    </label>
  );
}

export function Sources({ items, title }: { items: string[]; title: string }) {
  const unique = Array.from(new Set(items.filter(Boolean)));
  if (!unique.length) return null;
  return (
    <details className="sources">
      <summary>{title}</summary>
      <ol>
        {unique.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
    </details>
  );
}
