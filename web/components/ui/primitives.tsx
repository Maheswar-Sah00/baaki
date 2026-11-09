"use client";

// Small presentational pieces shared by the screens. No data fetching here: props in, events out.
// Class names are plain and styled in app/globals.css; colours come from app/theme.css tokens.
// See docs/DESIGN_SYSTEM.md. Existing props are stable: screens written against them still work.

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { formatTimer } from "@/lib/recorder";
import { inr, inrWhole } from "@/lib/format";
import type { Translate, UiLang } from "@/lib/i18n";
import { useT } from "@/hooks/useSettings";
import type { MeterChip } from "@/lib/types";
import type { PlayerState } from "@/hooks/useAudioPlayer";
import { MicIcon, PauseIcon, PlayIcon, ShieldIcon, StopIcon } from "./icons";
import { AppBar, BottomNav, Waveform, type NavKey } from "./kit";
import { ThemeToggle } from "./ThemeToggle";

// The design-system kit, re-exported so screens import everything from one place.
export {
  AppBar,
  BottomNav,
  BottomSheet,
  Card,
  Confetti,
  CountUp,
  GlowRing,
  GradientButton,
  HomesMap,
  MoneyFigure,
  Skeleton,
  SkeletonCard,
  StatusPill,
  Waveform,
  avatarTone,
  toneForState,
  type CardTone,
  type MapHome,
  type NavKey,
  type PillTone,
  type WashTone,
} from "./kit";
export { Illustration, ILLUSTRATIONS, type IllustrationName } from "./Illustration";
export { ThemeToggle } from "./ThemeToggle";
export { InstallButton } from "./InstallButton";

// ------------------------------------------------------------------ layout
const HTML_LANG: Record<UiLang, string> = { te: "te", "hi-en": "hi", en: "en" };

/**
 * App screen shell: AppBar (back, Cabinet title, theme toggle + Help; turns to glass on scroll), the
 * paper column (max 480 px, 16 px gutter, a calm pale frame around it on desktop), optional floating
 * pill BottomNav (`nav` = the active tab).
 */
export function Screen({
  title,
  back,
  children,
  className,
  safetyLink = true,
  themeToggle = true,
  nav,
  right,
  left,
  t,
  lang,
}: {
  title?: ReactNode;
  back?: string;
  children: ReactNode;
  className?: string;
  safetyLink?: boolean;
  themeToggle?: boolean;
  /** Show the bottom navigation with this tab active. */
  nav?: NavKey;
  /** Extra controls in the app bar, before the theme toggle. */
  right?: ReactNode;
  /** Replaces the back link on the left of the app bar (e.g. the brand on the home hub). */
  left?: ReactNode;
  t?: Translate;
  /**
   * HTML lang of the screen. Defaults to the worker's UI language on worker screens (those that pass
   * `t`), so Telugu / Devanagari get Indic type rules (no letter-spaced micro labels, roomier lines).
   */
  lang?: string;
}) {
  const showHead = title !== undefined || back || safetyLink || themeToggle || right || left;
  const { lang: uiLang } = useT();
  const htmlLang = lang ?? (t ? HTML_LANG[uiLang] : undefined);
  return (
    <main lang={htmlLang} className={`screen ${nav ? "screen-has-nav" : ""} ${className ?? ""}`}>
      {showHead ? (
        <AppBar
          title={title}
          back={back}
          left={left}
          backLabel={t ? t("common.back") : "Back"}
          right={
            <span className="appbar-actions">
              {right}
              {themeToggle ? <ThemeToggle /> : null}
              {safetyLink ? (
                <Link href="/safety" className="icon-btn icon-btn-safety" aria-label={t ? t("home.safety") : "Help"}>
                  <ShieldIcon />
                </Link>
              ) : null}
              {!themeToggle && !safetyLink && !right ? <span className="icon-btn-spacer" /> : null}
            </span>
          }
        />
      ) : null}
      {children}
      {nav ? <BottomNav t={t} active={nav} /> : null}
    </main>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <p className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>{" "}
      {label}
    </p>
  );
}

export function ErrorNote({ message, onRetry, retryLabel }: { message: string | null; onRetry?: () => void; retryLabel?: string }) {
  if (!message) return null;
  return (
    <div className="error-note" role="alert">
      <span className="error-note-icon" aria-hidden="true">!</span>
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
  const text = recording && elapsedMs !== undefined ? `${formatTimer(elapsedMs)} · ${label}` : label;
  if (size === "small") {
    // Compact recorder for cards and sheets: one pill-shaped button (40 px ink circle, label/timer,
    // a tiny live waveform). The whole pill is the press-to-talk target; a single hairline ring
    // follows the live level. No halos.
    return (
      <div className="mic-wrap mic-small" data-state={state}>
        <button
          type="button"
          className="mic-compact"
          data-state={state}
          style={{ "--level": level } as CSSProperties}
          disabled={disabled}
          aria-label={label}
          aria-pressed={recording}
          {...handlers}
        >
          <span className="mic-compact-dot" aria-hidden="true">
            {recording ? <StopIcon /> : <MicIcon />}
          </span>
          <span className="mic-compact-text mic-label" aria-live="polite">
            {text}
          </span>
          <Waveform active={recording} level={recording ? Math.max(0.25, level) : 0.15} bars={9} className="mic-compact-wave" />
        </button>
      </div>
    );
  }
  return (
    <div className={`mic-wrap mic-${size}`} data-state={state}>
      <span className="mic-stage" style={{ "--level": level } as CSSProperties}>
        <span className="mic-halo" aria-hidden="true" />
        <span className="mic-halo mic-halo-2" aria-hidden="true" />
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
      </span>
      <Waveform active={recording} level={recording ? Math.max(0.25, level) : 0.15} bars={22} className="mic-wave" />
      <p className="mic-label" aria-live="polite">
        {text}
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ Baaki Meter
export function MeterValue({ value, tick, animating, label }: { value: number; tick: number; animating: boolean; label: string }) {
  return (
    <div className="meter" data-animating={animating} data-tick={tick % 2}>
      <p className="meter-label">{label}</p>
      <div className="meter-stage">
        <span key={tick} className="meter-glow" aria-hidden="true" />
        <p className="meter-value" aria-live="polite" aria-atomic="true">
          {inrWhole(value)}
        </p>
      </div>
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
      <span className="play-btn-icon">{playing ? <PauseIcon /> : <PlayIcon />}</span>
      <span>{label}</span>
      <Waveform active={playing} bars={7} level={playing ? 0.8 : 0.3} className="play-btn-wave" />
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
