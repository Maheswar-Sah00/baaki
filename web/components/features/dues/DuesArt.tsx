// Small tile illustrations for the three kinds, in the Illustration.tsx style: flat rounded shapes on a soft blob,
// one ground shadow, fills from the --ill-* / --accent* tokens only (works in both palettes and themes).
import type { DuesKind } from "@/lib/features/dues";

export function DuesArt({ kind, size = 72 }: { kind: DuesKind; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <ellipse cx="48" cy="86" rx="28" ry="4" fill="var(--ill-shadow)" />
      <circle cx="48" cy="46" r="38" fill="var(--ill-blob)" />
      {kind === "vendor" ? <Milk /> : kind === "chit" ? <Chit /> : <Other />}
    </svg>
  );
}

function Milk() {
  return (
    <g>
      {/* milk can */}
      <rect x="22" y="34" width="30" height="44" rx="8" fill="var(--ill-paper)" stroke="var(--ill-line)" strokeWidth="2" />
      <rect x="27" y="26" width="20" height="10" rx="4" fill="var(--ill-paper-2)" stroke="var(--ill-line)" strokeWidth="2" />
      <path d="M30 26c0-6 14-6 14 0" fill="none" stroke="var(--ill-line)" strokeWidth="2.5" strokeLinecap="round" />
      <rect x="22" y="50" width="30" height="8" fill="var(--accent)" opacity="0.85" />
      {/* folded newspaper */}
      <rect x="52" y="46" width="26" height="32" rx="4" fill="var(--ill-paper)" stroke="var(--ill-line)" strokeWidth="2" transform="rotate(8 65 62)" />
      <path d="M57 54h14M57 60h16M57 66h12" stroke="var(--ill-line)" strokeWidth="2" strokeLinecap="round" transform="rotate(8 65 62)" opacity="0.6" />
      {/* rupee tag */}
      <circle cx="70" cy="28" r="10" fill="var(--ill-coin)" stroke="var(--ill-coin-2)" strokeWidth="2" />
      <path d="M66 24h8M66 28h8M68 24c5 0 5 6 0 6l5 5" fill="none" stroke="var(--accent-ink)" strokeWidth="1.8" strokeLinecap="round" />
    </g>
  );
}

function Chit() {
  return (
    <g>
      {/* calendar page with crossed-out weeks */}
      <rect x="18" y="22" width="40" height="44" rx="6" fill="var(--ill-paper)" stroke="var(--ill-line)" strokeWidth="2" />
      <rect x="18" y="22" width="40" height="10" rx="5" fill="var(--accent-2)" />
      <path d="M25 40l6 6M31 40l-6 6M39 40l6 6M45 40l-6 6M25 52l6 6M31 52l-6 6" stroke="var(--error)" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="42" cy="55" r="4" fill="none" stroke="var(--ill-line)" strokeWidth="2" />
      {/* coin stack */}
      <ellipse cx="66" cy="76" rx="14" ry="5" fill="var(--ill-coin-2)" />
      <rect x="52" y="60" width="28" height="16" fill="var(--ill-coin)" />
      <ellipse cx="66" cy="60" rx="14" ry="5" fill="var(--ill-coin-2)" />
      <rect x="52" y="48" width="28" height="12" fill="var(--ill-coin)" />
      <ellipse cx="66" cy="48" rx="14" ry="5" fill="var(--ill-coin)" stroke="var(--ill-coin-2)" strokeWidth="2" />
      <path d="M62 46h8M62 49h8" stroke="var(--accent-ink)" strokeWidth="1.6" strokeLinecap="round" />
    </g>
  );
}

function Other() {
  return (
    <g>
      {/* notebook (the khata) */}
      <rect x="24" y="20" width="40" height="54" rx="6" fill="var(--ill-paper)" stroke="var(--ill-line)" strokeWidth="2" />
      <rect x="24" y="20" width="9" height="54" rx="4" fill="var(--accent)" />
      <path d="M40 34h17M40 42h17M40 50h12" stroke="var(--ill-line)" strokeWidth="2" strokeLinecap="round" opacity="0.6" />
      {/* speech bubble: "next week" */}
      <path d="M54 52h24a6 6 0 0 1 6 6v10a6 6 0 0 1-6 6H66l-6 6v-6h-6a6 6 0 0 1-6-6V58a6 6 0 0 1 6-6z" fill="var(--accent-soft)" stroke="var(--accent-line)" strokeWidth="2" />
      <circle cx="61" cy="63" r="2.2" fill="var(--accent-text)" />
      <circle cx="68" cy="63" r="2.2" fill="var(--accent-text)" />
      <circle cx="75" cy="63" r="2.2" fill="var(--accent-text)" />
    </g>
  );
}
