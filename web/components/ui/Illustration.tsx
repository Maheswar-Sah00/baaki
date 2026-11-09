"use client";

// Baaki's original illustration set, pale editorial: flat rounded shapes on a pale wash, one ground
// shadow, warm skin tones, cloth in pale lilac / peach, ink accents. Calm: no sparkles, no glow.
// Every fill comes from --ill-* / --accent* tokens (app/theme.css), so each picture follows the
// palette and the light/dark theme. Classes are styled in app/globals.css (".ill ...").
//
//   <Illustration name="speak" />                 decorative (aria-hidden)
//   <Illustration name="coins" title="Money owed" /> meaningful (role="img" + <title>)
//   <Illustration name="speak" animated size={220} /> gentle float + live waveform (reduced-motion safe)
//
// Supplied art wins: when /assets/ill-<name>.webp exists (a flat cartoon on a transparent background)
// it is shown as an <img> in the same 4:3 box (object-fit: contain), floating gently when `animated`.
// Missing file -> this inline SVG, with the same detection as <AssetSlot> (components/ui/asset-probe.ts).

import { useId, type CSSProperties } from "react";
import { useAssetStatus } from "./asset-probe";

export type IllustrationName =
  | "speak"
  | "home"
  | "coins"
  | "handshake"
  | "shield"
  | "celebrate"
  | "empty"
  | "wave"
  | "send";

export const ILLUSTRATIONS: IllustrationName[] = ["speak", "home", "coins", "handshake", "shield", "celebrate", "empty", "wave", "send"];

type Props = {
  name: IllustrationName;
  title?: string;
  size?: number | string;
  animated?: boolean;
  className?: string;
  style?: CSSProperties;
};

export function Illustration({ name, title, size, animated = false, className, style }: Props) {
  const raw = useId();
  const id = `ill${raw.replace(/[^a-zA-Z0-9]/g, "")}`;
  const g = `url(#${id}g)`;
  const Art = ART[name];
  const src = `/assets/ill-${name}.webp`;
  const { status, ref, onLoad, onError } = useAssetStatus(src);
  if (status !== "missing") {
    return (
      <span
        className={`ill ill-img ill-${name} ${animated ? "ill-anim" : ""} ${className ?? ""}`}
        data-loaded={status === "ok"}
        style={{ width: size ?? "100%", ...style }}
        role={title ? "img" : undefined}
        aria-label={title}
        aria-hidden={title ? undefined : true}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img ref={ref} src={src} alt="" decoding="async" onLoad={onLoad} onError={onError} />
      </span>
    );
  }
  return (
    <svg
      viewBox="0 0 240 180"
      className={`ill ill-${name} ${animated ? "ill-anim" : ""} ${className ?? ""}`}
      style={{ width: size ?? "100%", height: "auto", ...style }}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <defs>
        <linearGradient id={`${id}g`} x1="0" y1="0" x2="1" y2="1">
          {/* solid ink accent (white in dark): the "gradient" is flat on purpose */}
          <stop offset="0" style={{ stopColor: "var(--ink-pill, var(--text))" }} />
          <stop offset="1" style={{ stopColor: "var(--ink-pill, var(--text))" }} />
        </linearGradient>
      </defs>
      <Art g={g} />
    </svg>
  );
}

type ArtProps = { g: string };

const Blob = ({ alt = false }: { alt?: boolean }) => (
  <path
    className={alt ? "b2" : "b1"}
    d="M40 98c-6-38 26-70 66-74 30-3 44 10 72 12 30 2 46 26 40 56-6 32-30 58-72 62-36 4-52-10-76-12-20-2-26-18-30-44z"
  />
);

const Shadow = ({ cx = 120, cy = 166, rx = 70 }: { cx?: number; cy?: number; rx?: number }) => (
  <ellipse className="sh" cx={cx} cy={cy} rx={rx} ry="7" />
);

/** Sparkles were retired in the pale redesign (no shiny things); kept as a no-op so the art reads the same. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Spark = (_: { x: number; y: number; s?: number; cls?: string }) => null;

const RupeeMark = ({ x, y, s = 1, cls = "ink" }: { x: number; y: number; s?: number; cls?: string }) => (
  <path
    className={`${cls} ill-stroke`}
    transform={`translate(${x} ${y}) scale(${s})`}
    d="M-6-8H6M-6-3H6M-3-8c6 0 6 10 0 10h-3l9 8"
  />
);

const Bars = ({ x, y, g, n = 7, h = 26, w = 5, gap = 4 }: { x: number; y: number; g: string; n?: number; h?: number; w?: number; gap?: number }) => {
  const shape = [0.35, 0.7, 1, 0.55, 0.85, 0.45, 0.75, 0.4, 0.9, 0.5];
  return (
    <g className="ill-bars">
      {Array.from({ length: n }, (_, i) => {
        const bh = Math.max(6, h * shape[i % shape.length]);
        return (
          <rect
            key={i}
            x={x + i * (w + gap)}
            y={y - bh / 2}
            width={w}
            height={bh}
            rx={w / 2}
            fill={g}
            style={{ animationDelay: `${i * 90}ms` }}
          />
        );
      })}
    </g>
  );
};

/** A woman speaking into her phone; sound comes out as the brand waveform. */
function Speak({ g }: ArtProps) {
  return (
    <>
      <Blob />
      <Shadow />
      <g className="ill-float">
        {/* body + sari */}
        <path className="c1" d="M58 168c2-34 26-52 62-54 36 2 58 20 60 54z" />
        <path className="c2" d="M96 118c22 14 50 22 72 40l8 10h-26c-12-16-34-28-60-40z" />
        <path className="c1-dark" d="M112 116h16l-8 12z" />
        {/* neck + head */}
        <rect className="sk2" x="111" y="96" width="18" height="24" rx="8" />
        <circle className="sk" cx="120" cy="80" r="25" />
        {/* hair + bun (she faces right, towards the phone) */}
        <path className="hr" d="M95 84c-3-24 12-34 27-34 17 0 28 10 25 27-6-7-16-11-28-9-11 2-18 9-20 22z" />
        <circle className="hr" cx="96" cy="62" r="11" />
        <path className="coin ill-flower" d="M90 54a4 4 0 1 1 6 4 4 4 0 1 1-6-4z" />
        {/* face */}
        <circle className="c1" cx="129" cy="70" r="2" />
        <ellipse className="hr" cx="134" cy="80" rx="2.2" ry="2.6" />
        <path className="ln ill-stroke" d="M131 92c3 2 7 2 9-1" />
        <circle className="coin" cx="104" cy="92" r="3" />
        {/* arm + phone */}
        <path className="sk ill-arm" d="M150 160c6-18 8-34 2-52l-10 2c4 16 2 32-4 48z" />
        <g transform="rotate(-14 156 88)">
          <rect className="ph" x="146" y="70" width="20" height="36" rx="5" />
          <rect className="sc" x="149" y="75" width="14" height="26" rx="2.5" />
          <circle className="ac" cx="156" cy="88" r="3.5" />
        </g>
        <circle className="sk" cx="149" cy="105" r="8" />
      </g>
      {/* voice */}
      <path className="ac ill-stroke ill-arc ill-arc1" d="M176 72c6 6 6 16 0 22" />
      <path className="ac ill-stroke ill-arc ill-arc2" d="M186 64c11 10 11 28 0 38" />
      <Bars x={196} y={84} g={g} n={4} h={30} w={5} gap={4} />
      <Spark x={70} y={46} s={0.9} />
      <Spark x={200} y={124} s={0.7} cls="c1" />
    </>
  );
}

/** One home = one card: house, rupee pin, the money still owed. */
function Home({ g }: ArtProps) {
  return (
    <>
      <Blob alt />
      <Shadow rx={64} />
      <g className="ill-float">
        <rect className="pp ill-card" x="52" y="38" width="136" height="112" rx="18" />
        <rect className="pp2" x="64" y="50" width="112" height="62" rx="12" />
        <path className="rf" d="M86 84l34-26 34 26z" />
        <rect className="pp" x="92" y="82" width="56" height="28" rx="3" />
        <rect className="wn" x="99" y="88" width="12" height="10" rx="2" />
        <rect className="wn" x="129" y="88" width="12" height="10" rx="2" />
        <rect className="c1" x="114" y="92" width="12" height="18" rx="2" />
        <circle className="lf" cx="76" cy="104" r="8" />
        <circle className="lf" cx="164" cy="104" r="6" />
        <rect className="line" x="64" y="122" width="62" height="8" rx="4" />
        <rect className="line" x="64" y="134" width="40" height="6" rx="3" />
        <rect fill={g} x="140" y="120" width="36" height="20" rx="10" />
      </g>
      <g className="ill-pin">
        <circle fill={g} cx="182" cy="42" r="20" />
        <circle className="glow-ring" cx="182" cy="42" r="26" />
        <RupeeMark x={182} y={42} s={1.1} />
      </g>
      <Spark x={46} y={54} s={0.8} />
    </>
  );
}

/** Coins and a note: the money. */
function Coins({ g }: ArtProps) {
  const stack = (x: number, n: number) =>
    Array.from({ length: n }, (_, i) => (
      <g key={i}>
        <ellipse className="coin2" cx={x} cy={148 - i * 11 + 4} rx="22" ry="8" />
        <ellipse className="coin" cx={x} cy={148 - i * 11} rx="22" ry="8" />
      </g>
    ));
  return (
    <>
      <Blob />
      <Shadow rx={78} />
      <g className="ill-float">
        <g transform="rotate(-10 120 80)">
          <rect className="lf" x="74" y="44" width="96" height="52" rx="8" />
          <rect className="pp" x="80" y="50" width="84" height="40" rx="5" opacity="0.35" />
          <circle className="pp" cx="122" cy="70" r="13" opacity="0.7" />
          <RupeeMark x={122} y={70} s={0.8} cls="ink" />
        </g>
        {stack(84, 4)}
        {stack(130, 6)}
        {stack(174, 3)}
        <ellipse fill={g} cx="130" cy="93" rx="22" ry="8" />
        <RupeeMark x={130} y={93} s={0.55} />
      </g>
      <Spark x={196} y={58} />
      <Spark x={52} y={96} s={0.7} cls="c1" />
    </>
  );
}

/** A handshake: an agreement kept. */
function Handshake({ g }: ArtProps) {
  return (
    <>
      <Blob alt />
      <Shadow rx={74} />
      <g className="ill-float">
        <path className="c1" d="M34 136l44-36 18 22-42 34z" />
        <path className="c2" d="M206 136l-44-36-18 22 42 34z" />
        <path className="sk2" d="M74 100c14-12 30-16 46-12l22 6-8 14-20-4c-8 8-20 14-32 12z" />
        <path className="sk" d="M166 100c-12-10-28-14-44-10l-30 10c-6 2-6 10 0 12l20-2 6 6c6 8 18 10 26 4l14-8z" />
        <path className="ln ill-stroke" d="M132 112l8 8M124 116l7 7M116 118l5 5" opacity="0.5" />
      </g>
      <path fill={g} className="ill-heart" d="M120 58c-6-10-22-8-22 4 0 10 14 18 22 24 8-6 22-14 22-24 0-12-16-14-22-4z" />
      <Spark x={74} y={52} s={0.8} />
      <Spark x={170} y={46} s={0.9} cls="c1" />
    </>
  );
}

/** Safety: a shield with a check. */
function Shield({ g }: ArtProps) {
  return (
    <>
      <Blob />
      <Shadow rx={56} />
      <circle className="glow-ring ill-pulse" cx="120" cy="90" r="62" />
      <g className="ill-float">
        <path fill={g} d="M120 30l52 18v34c0 36-24 60-52 72-28-12-52-36-52-72V48z" />
        <path className="pp" opacity="0.22" d="M120 42l40 14v26c0 28-18 48-40 58z" />
        <path className="on-grad ill-stroke ill-check" d="M98 92l15 15 30-32" strokeWidth="8" />
      </g>
      <Spark x={186} y={46} />
      <Spark x={58} y={130} s={0.7} cls="c1" />
    </>
  );
}

/** "Paisa aa gaya": phone with the money in, confetti all round. */
function Celebrate({ g }: ArtProps) {
  const bits = [
    [52, 40, "c1", 20],
    [78, 24, "c2", -30],
    [168, 22, "ac", 45],
    [196, 50, "c1", 10],
    [206, 96, "c2", -20],
    [40, 92, "ac", 30],
    [60, 130, "lf", -10],
    [188, 136, "lf", 60],
  ] as const;
  return (
    <>
      <Blob alt />
      <Shadow rx={60} />
      {bits.map(([x, y, c, r], i) => (
        <rect key={i} className={`${c} ill-confetti`} x={x} y={y} width="9" height="5" rx="1.5" transform={`rotate(${r} ${x} ${y})`} style={{ animationDelay: `${i * 120}ms` }} />
      ))}
      <circle className="coin ill-confetti" cx="150" cy="30" r="4" />
      <circle className="c1 ill-confetti" cx="92" cy="150" r="3.5" />
      <g className="ill-float">
        <rect className="ph" x="88" y="34" width="64" height="118" rx="14" />
        <rect className="sc" x="94" y="44" width="52" height="98" rx="8" />
        <circle fill={g} cx="120" cy="82" r="20" />
        <path className="on-grad ill-stroke" d="M111 82l6 6 12-13" strokeWidth="4.5" />
        <rect fill={g} x="102" y="112" width="36" height="8" rx="4" />
        <rect className="line" x="106" y="124" width="28" height="5" rx="2.5" />
      </g>
      <g className="ill-coin-pop">
        <ellipse className="coin2" cx="176" cy="118" rx="14" ry="14" />
        <circle className="coin" cx="174" cy="116" r="13" />
        <RupeeMark x={174} y={116} s={0.6} />
      </g>
      <Spark x={64} y={70} />
      <Spark x={182} y={78} s={0.8} cls="c1" />
    </>
  );
}

/** Nothing here yet: a dotted outline of a home and a little mic. */
function Empty({ g }: ArtProps) {
  return (
    <>
      <Blob />
      <Shadow rx={56} />
      <rect className="dash" x="60" y="44" width="120" height="100" rx="18" />
      <path className="dash" d="M92 100l28-22 28 22v28H92z" />
      <g className="ill-float">
        <circle fill={g} cx="168" cy="132" r="22" />
        <rect className="on-grad-fill" x="163" y="120" width="10" height="16" rx="5" />
        <path className="on-grad ill-stroke" d="M159 132a9 9 0 0 0 18 0M168 141v4" strokeWidth="2.5" />
      </g>
      <Spark x={70} y={40} s={0.7} />
    </>
  );
}

/** A voice-note bubble with the waveform. */
function Wave({ g }: ArtProps) {
  return (
    <>
      <Blob alt />
      <Shadow rx={70} />
      <g className="ill-float">
        <path className="pp ill-card" d="M44 58a18 18 0 0 1 18-18h116a18 18 0 0 1 18 18v52a18 18 0 0 1-18 18H92l-26 20 4-20h-8a18 18 0 0 1-18-18z" />
        <circle fill={g} cx="76" cy="84" r="16" />
        <path className="on-grad-fill" d="M71 76v16l13-8z" />
        <Bars x={102} y={84} g={g} n={9} h={34} w={5} gap={4} />
      </g>
      <Spark x={200} y={40} />
    </>
  );
}

/** Sent: a voice note delivered, double tick. */
function Send({ g }: ArtProps) {
  return (
    <>
      <Blob />
      <Shadow rx={66} />
      <path className="ac ill-stroke ill-trail" d="M22 112h30M30 126h20M36 98h14" opacity="0.6" />
      <g className="ill-float">
        <path className="pp ill-card" d="M60 54a16 16 0 0 1 16-16h112a16 16 0 0 1 16 16v54a16 16 0 0 1-16 16h-8l6 18-26-18H76a16 16 0 0 1-16-16z" />
        <circle fill={g} cx="88" cy="80" r="14" />
        <path className="on-grad-fill" d="M84 73v14l11-7z" />
        <Bars x={110} y={80} g={g} n={8} h={28} w={4.5} gap={4} />
        <path className="ok ill-stroke" d="M160 108l5 5 9-10M168 113l9-10" strokeWidth="2.6" />
      </g>
      <Spark x={206} y={44} s={0.9} />
    </>
  );
}

const ART: Record<IllustrationName, (p: ArtProps) => React.ReactElement> = {
  speak: Speak,
  home: Home,
  coins: Coins,
  handshake: Handshake,
  shield: Shield,
  celebrate: Celebrate,
  empty: Empty,
  wave: Wave,
  send: Send,
};
