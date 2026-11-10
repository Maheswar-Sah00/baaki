"use client";

// Baaki design-system components (docs/DESIGN_SYSTEM.md). Presentational only: props in, events
// out, no data fetching. Styles live in app/globals.css under the same class names; colours come
// from app/theme.css tokens.

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ElementType,
  type ReactNode,
} from "react";
import type { Translate } from "@/lib/i18n";
import { inrWhole } from "@/lib/format";
import { easeOutCubic, prefersReducedMotion } from "@/lib/easing";
import { BackIcon, CrossIcon, DiaryIcon, HomeIcon, MicIcon, ShieldIcon, WaveIcon } from "./icons";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

// ------------------------------------------------------------------ AppBar
/** Sticky glass top bar: back link (or spacer), centred title, right slot (defaults to nothing). */
export function AppBar({
  title,
  back,
  backLabel = "Back",
  right,
  left,
  className,
}: {
  title?: ReactNode;
  back?: string;
  backLabel?: string;
  right?: ReactNode;
  left?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cx("appbar screen-head", className)}>
      {left ??
        (back ? (
          <Link href={back} className="icon-btn" aria-label={backLabel}>
            <BackIcon />
          </Link>
        ) : (
          <span className="icon-btn-spacer" />
        ))}
      {title !== undefined ? <h1 className="screen-title">{title}</h1> : <span />}
      {right ?? <span className="icon-btn-spacer" />}
    </header>
  );
}

// ------------------------------------------------------------------ BottomNav
export type NavKey = "home" | "diary" | "speak" | "voice" | "safety";

const NAV: { key: NavKey; href: string; label: Parameters<Translate>[0]; Icon: (p: { className?: string }) => ReactNode }[] = [
  { key: "home", href: "/app", label: "common.home", Icon: HomeIcon },
  { key: "diary", href: "/diary", label: "home.diary", Icon: DiaryIcon },
  { key: "speak", href: "/speak", label: "home.speak", Icon: MicIcon },
  { key: "voice", href: "/voice", label: "home.voice", Icon: WaveIcon },
  { key: "safety", href: "/safety", label: "home.safety", Icon: ShieldIcon },
];

/** Uber-style bottom bar with a raised gradient mic in the middle. Active tab from `active` or the URL. */
export function BottomNav({ t, active }: { t?: Translate; active?: NavKey }) {
  const path = usePathname();
  const current = active ?? NAV.find((n) => n.href === path)?.key;
  return (
    <nav className="bottom-nav" aria-label="Main">
      {NAV.map(({ key, href, label, Icon }) => {
        const text = t ? t(label) : key;
        const on = current === key;
        return (
          <Link
            key={key}
            href={href}
            className={cx("bottom-nav-item", key === "speak" && "bottom-nav-speak")}
            aria-current={on ? "page" : undefined}
            aria-label={key === "speak" ? text : undefined}
          >
            <span className="bottom-nav-icon">
              <Icon />
            </span>
            <span className="bottom-nav-label">{text}</span>
          </Link>
        );
      })}
    </nav>
  );
}

// ------------------------------------------------------------------ BottomSheet
/**
 * Modal sheet that slides up from the bottom (centred dialog on wide screens).
 * Closes on Escape, scrim tap and the close button. Keep content short; one primary action.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  children,
  closeLabel = "Close",
  className,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  closeLabel?: string;
  className?: string;
}) {
  const [mounted, setMounted] = useState(open);
  const [closing, setClosing] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();

  if (open && !mounted) {
    setMounted(true);
    setClosing(false);
  }
  if (!open && mounted && !closing) setClosing(true);

  useEffect(() => {
    if (!closing) return;
    const timer = window.setTimeout(() => {
      setMounted(false);
      setClosing(false);
    }, prefersReducedMotion() ? 0 : 220);
    return () => window.clearTimeout(timer);
  }, [closing]);

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prev?.focus?.();
    };
  }, [open, onClose]);

  if (!mounted) return null;
  return (
    <div className="sheet-root" data-state={closing ? "closing" : "open"}>
      <div className="sheet-scrim" onClick={onClose} aria-hidden="true" />
      <div
        ref={panel}
        className={cx("sheet", className)}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
      >
        <span className="sheet-handle" aria-hidden="true" />
        <div className="sheet-head">
          {title ? (
            <h2 id={titleId} className="sheet-title">
              {title}
            </h2>
          ) : (
            <span />
          )}
          <button type="button" className="icon-btn" onClick={onClose} aria-label={closeLabel}>
            <CrossIcon />
          </button>
        </div>
        <div className="sheet-body">{children}</div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Card
export type CardTone =
  | "default"
  | "glow"
  | "gradient"
  | "soft"
  | "success"
  | "warn"
  // pale washes (pale palette) and a solid ink card
  | "sky"
  | "lilac"
  | "peach"
  | "butter"
  | "sage"
  | "rose"
  | "ink";

/**
 * Surface for one idea: white card + 1px hairline. tone="glow" = the emphasised card (darker hairline,
 * no glow; once per screen). Pale washes: sky | lilac | peach | butter | sage | rose. "gradient" and
 * "ink" = solid ink card (celebration only).
 */
export function Card({
  children,
  tone = "default",
  as,
  href,
  className,
  style,
  ...rest
}: {
  children: ReactNode;
  tone?: CardTone;
  as?: ElementType;
  href?: string;
  className?: string;
  style?: CSSProperties;
} & Record<string, unknown>) {
  const cls = cx("card", "ds-card", href && "card-link", className);
  if (href) {
    return (
      <Link href={href} className={cls} data-tone={tone} style={style} {...rest}>
        {children}
      </Link>
    );
  }
  const Tag = (as ?? "div") as ElementType;
  return (
    <Tag className={cls} data-tone={tone} style={style} {...rest}>
      {children}
    </Tag>
  );
}

// ------------------------------------------------------------------ StatusPill
export type PillTone = "neutral" | "accent" | "success" | "warn" | "error" | "estimate" | "live";

/** Small rounded status label: pale tint + ink text, with a dot. tone="live" pulses (recording, sending). */
export function StatusPill({ tone = "neutral", children, dot = true, className }: { tone?: PillTone; children: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span className={cx("pill", className)} data-tone={tone}>
      {dot ? <span className="pill-dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

/** Maps a case state (lib/types) to a pill tone. */
export function toneForState(state: string | null | undefined): PillTone {
  switch (state) {
    case "paid":
    case "clear":
    case "sent":
      return "success";
    case "partly_paid":
    case "ignored":
    case "below_minimum":
      return "warn";
    case "draft":
      return "accent";
    default:
      return "neutral";
  }
}

// ------------------------------------------------------------------ avatarTone
export type WashTone = "sky" | "lilac" | "rose" | "peach" | "butter" | "sage";
const AVATAR_WASHES: WashTone[] = ["sky", "lilac", "rose", "peach", "butter", "sage"];

/**
 * One stable pale wash per person, from the first word of the name, so a home (or a person who owes
 * her) has the same colour on every screen: <span className="hub-avatar" data-tone={avatarTone(name)}>.
 * Demo story: Sharma = sky, Reddy = peach, Mehta = lilac, Rao = sage.
 */
export function avatarTone(name: string | null | undefined): WashTone {
  const key = (name ?? "").trim().toLowerCase().split(/\s+/)[0] ?? "";
  let x = 7;
  for (const ch of key) x = (x * 13 + (ch.codePointAt(0) ?? 0)) % 1000003;
  return AVATAR_WASHES[x % AVATAR_WASHES.length];
}

// ------------------------------------------------------------------ GradientButton
/** The one big primary action: solid ink pill (white in dark), press scale. Link when `href` is set. */
export function GradientButton({
  children,
  href,
  onClick,
  icon,
  size = "lg",
  disabled,
  type = "button",
  className,
  ...rest
}: {
  children: ReactNode;
  href?: string;
  onClick?: () => void;
  icon?: ReactNode;
  size?: "md" | "lg";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
} & Record<string, unknown>) {
  const cls = cx("btn", "btn-primary", "btn-grad", size === "lg" && "btn-big", className);
  const inner = (
    <>
      {icon}
      <span>{children}</span>
    </>
  );
  if (href && !disabled) {
    return (
      <Link href={href} className={cls} {...rest}>
        {inner}
      </Link>
    );
  }
  return (
    <button type={type} className={cls} onClick={onClick} disabled={disabled} {...rest}>
      {inner}
    </button>
  );
}

// ------------------------------------------------------------------ GlowRing
/** Calm concentric hairline rings that breathe around any round child (the mic). `level` 0..1 swells them live. */
export function GlowRing({ children, active = true, level = 0, className }: { children: ReactNode; active?: boolean; level?: number; className?: string }) {
  return (
    <span className={cx("glow-ring-wrap", className)} data-active={active} style={{ "--level": level } as CSSProperties}>
      <span className="glow-ring-halo" aria-hidden="true" />
      <span className="glow-ring-halo glow-ring-halo-2" aria-hidden="true" />
      {children}
    </span>
  );
}

// ------------------------------------------------------------------ Waveform
/**
 * Crisp ink voice bars. `active` animates them; `level` (0..1, e.g. the mic
 * level from usePressToTalk) scales their height live. Static and short when idle.
 */
export function Waveform({ active = true, level, bars = 24, className, label }: { active?: boolean; level?: number; bars?: number; className?: string; label?: string }) {
  return (
    <span
      className={cx("waveform", className)}
      data-active={active}
      style={{ "--level": level ?? 0.6 } as CSSProperties}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {Array.from({ length: bars }, (_, i) => (
        <span
          key={i}
          className="waveform-bar"
          style={{ "--i": i, "--h": WAVE_SHAPE[i % WAVE_SHAPE.length] } as CSSProperties}
        />
      ))}
    </span>
  );
}
const WAVE_SHAPE = [0.4, 0.7, 0.55, 0.95, 0.6, 0.8, 0.35, 0.9, 0.5, 0.75, 0.45, 1, 0.65, 0.4, 0.85, 0.55];

// ------------------------------------------------------------------ Skeleton
/** Shimmering placeholder. Use the same shape as the content it stands in for. */
export function Skeleton({
  width = "100%",
  height = 16,
  radius,
  lines,
  className,
}: {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  lines?: number;
  className?: string;
}) {
  if (lines && lines > 1) {
    return (
      <span className={cx("skeleton-lines", className)} aria-hidden="true">
        {Array.from({ length: lines }, (_, i) => (
          <span key={i} className="skeleton" style={{ width: i === lines - 1 ? "62%" : width, height, borderRadius: radius }} />
        ))}
      </span>
    );
  }
  return <span className={cx("skeleton", className)} aria-hidden="true" style={{ width, height, borderRadius: radius }} />;
}

/** Skeleton of a home card (dashboard loading state). */
export function SkeletonCard() {
  return (
    <div className="card skeleton-card" aria-hidden="true">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <Skeleton width="45%" height={18} />
        <Skeleton width={70} height={22} radius={999} />
      </div>
      <Skeleton width="60%" height={26} />
      <Skeleton width="80%" height={12} />
    </div>
  );
}

// ------------------------------------------------------------------ Confetti
const CONFETTI_COLORS = ["var(--confetti-1)", "var(--confetti-2)", "var(--confetti-3)", "var(--confetti-4)"];
/** Falling confetti over the parent (position: relative/fixed parent). Hidden with reduced motion. */
export function Confetti({ pieces = 36, className }: { pieces?: number; className?: string }) {
  return (
    <span className={cx("confetti", className)} aria-hidden="true">
      {Array.from({ length: pieces }, (_, i) => {
        // deterministic pseudo-random so server and client agree
        const r = (n: number) => ((Math.sin(i * 9301 + n * 49297) + 1) / 2) % 1;
        return (
          <span
            key={i}
            className="confetti-piece"
            data-shape={i % 3}
            style={
              {
                "--x": `${Math.round(r(1) * 100)}%`,
                "--d": `${(r(2) * 0.9).toFixed(2)}s`,
                "--t": `${(2.2 + r(3) * 1.6).toFixed(2)}s`,
                "--r": `${Math.round(r(4) * 720 - 360)}deg`,
                "--drift": `${Math.round(r(5) * 80 - 40)}px`,
                background: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
              } as CSSProperties
            }
          />
        );
      })}
    </span>
  );
}

// ------------------------------------------------------------------ CountUp
/** Counts from 0 to `value` when first visible. Formats as ₹ unless `format` is given. */
export function CountUp({
  value,
  durationMs = 1400,
  format,
  className,
}: {
  value: number;
  durationMs?: number;
  format?: (n: number) => string;
  className?: string;
}) {
  // Server render shows the final number (no-JS, print, crawlers); on mount it resets to 0 and
  // counts up once the number scrolls into view.
  const [shown, setShown] = useState(value);
  const el = useRef<HTMLSpanElement>(null);
  const fmt = useCallback((n: number) => (format ? format(n) : inrWhole(n)), [format]);

  useEffect(() => {
    const node = el.current;
    if (!node) return;
    // Reduced motion, or nothing to count (still loading): show the value as it is. `shown` is state, so a
    // value that arrives after mount (data loaded) must still be written, or the figure stays at 0.
    if (prefersReducedMotion() || value === 0) {
      const raf = requestAnimationFrame(() => setShown(value));
      return () => cancelAnimationFrame(raf);
    }
    let raf = requestAnimationFrame(() => setShown(0));
    const run = () => {
      const t0 = performance.now();
      const step = (now: number) => {
        // rAF timestamps can be a little earlier than t0: clamp, so the first frame never goes below 0
        const p = Math.min(1, Math.max(0, (now - t0) / durationMs));
        setShown(Math.round(value * easeOutCubic(p)));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    };
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          run();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(node);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value, durationMs]);

  return (
    <span ref={el} className={cx("count-up", className)}>
      {fmt(shown)}
    </span>
  );
}

// ------------------------------------------------------------------ MoneyFigure
/**
 * Big money figure: a small muted ₹ and Cabinet Grotesk tabular digits in ink (never gradient).
 * `count` counts up once when it scrolls into view (`durationMs`, default CountUp's 1400 ms).
 * size: sm (24) · md (34) · lg (52) · xl (64).
 */
export function MoneyFigure({
  value,
  count = false,
  durationMs,
  size = "lg",
  className,
}: {
  value: number;
  count?: boolean;
  durationMs?: number;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  const digits = (n: number) => inrWhole(n).replace("₹", "");
  return (
    <span className={cx("figure", `figure-${size}`, className)}>
      <span className="figure-cur">₹</span>
      {count ? (
        <CountUp value={value} format={digits} durationMs={durationMs} className="figure-num" />
      ) : (
        <span className="figure-num">{digits(value)}</span>
      )}
    </span>
  );
}

// ------------------------------------------------------------------ HomesMap
export type MapHome = { id: string | number; name: string; amount: number; tone?: PillTone; href?: string };

// Pin tips (pins hang above their tip). Spread so labels never cover "you" at (46%, 66%).
const ROADS = [
  "M-5 40 C 20 36, 40 46, 60 40 S 90 30, 105 34",
  "M-5 78 C 25 70, 45 82, 70 74 S 95 66, 105 70",
  "M30 -5 C 34 20, 26 50, 34 105",
  "M76 -5 C 70 30, 80 60, 72 105",
];
const LANES = ["M34 58 H 74", "M52 40 V 76", "M8 20 C 16 24, 22 22, 31 18", "M76 52 C 84 50, 92 54, 104 52", "M34 92 H 72"];

const PIN_SLOTS = [
  { x: 22, y: 40 },
  { x: 74, y: 30 },
  { x: 76, y: 86 },
  { x: 20, y: 92 },
  { x: 90, y: 62 },
  { x: 48, y: 26 },
];

/**
 * Pale paper map: hairline roads, a lake and a park, one ink pin per home with an amount chip.
 * Pins sit in fixed slots, so up to 6 homes; the first chip is solid ink.
 */
export function HomesMap({ homes, you = "You", className, label }: { homes: MapHome[]; you?: string; className?: string; label?: string }) {
  const shown = homes.slice(0, PIN_SLOTS.length);
  return (
    <div className={cx("homes-map", className)} role="group" aria-label={label}>
      <svg className="homes-map-roads" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path className="homes-map-water" d="M58 -2 C 64 10, 92 8, 102 14 L 102 -2 Z" />
        <path className="homes-map-park" d="M4 56 h18 a3 3 0 0 1 3 3 v10 a3 3 0 0 1 -3 3 h-18 a3 3 0 0 1 -3 -3 v-10 a3 3 0 0 1 3 -3 z" />
        <path className="homes-map-park" d="M84 80 h12 a3 3 0 0 1 3 3 v14 h-18 v-14 a3 3 0 0 1 3 -3 z" />
        {ROADS.map((d, i) => (
          <path key={`c${i}`} className="homes-map-casing" d={d} />
        ))}
        {ROADS.map((d, i) => (
          <path key={`r${i}`} className="homes-map-road" d={d} />
        ))}
        {LANES.map((d, i) => (
          <path key={`l${i}`} className="homes-map-lane" d={d} />
        ))}
        <path className="homes-map-route" d="M46 66 C 40 58, 30 50, 22 42" />
      </svg>
      <span className="homes-map-you" style={{ left: "46%", top: "66%" }}>
        <span className="homes-map-you-dot" />
        <span className="homes-map-you-label">{you}</span>
      </span>
      {shown.map((h, i) => {
        const slot = PIN_SLOTS[i];
        const body = (
          <>
            <span className="homes-map-pin-name">{h.name}</span>
            <span className="homes-map-pin-amount">{inrWhole(h.amount)}</span>
          </>
        );
        const style = { left: `${slot.x}%`, top: `${slot.y}%`, animationDelay: `${200 + i * 140}ms` } as CSSProperties;
        return h.href ? (
          <Link key={h.id} href={h.href} className="homes-map-pin" data-tone={h.tone ?? "accent"} data-first={i === 0} style={style}>
            {body}
          </Link>
        ) : (
          <span key={h.id} className="homes-map-pin" data-tone={h.tone ?? "accent"} data-first={i === 0} style={style}>
            {body}
          </span>
        );
      })}
    </div>
  );
}
