// Small line glyphs for the Fair Pay Check (stroke = currentColor, like components/ui/icons.tsx).

type P = { className?: string };
const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export const BroomGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M14 3l-3.5 9" />
    <path d="M7 12h7l2 9H5l2-9z" />
    <path d="M9 16v5M12 16v5" />
  </svg>
);

export const PotGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 10h16v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5v-5z" />
    <path d="M2 10h2M20 10h2" />
    <path d="M9 6c0-1 1-1.5 1-2.5M13 6c0-1 1-1.5 1-2.5" />
  </svg>
);

export const BothGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v10h14V10" />
    <path d="M9 20v-5h6v5" />
  </svg>
);

export const CareGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
    <path d="M9.5 11.5h5M12 9v5" />
  </svg>
);

export const HeartGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
  </svg>
);

export const CalendarGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <rect x="4" y="5" width="16" height="15" rx="3" />
    <path d="M8 3v4M16 3v4M4 10h16" />
    <path d="M10 15l1.5 1.5L15 13" />
  </svg>
);

export const UsersGlyph = ({ className }: P) => (
  <svg {...base} className={className}>
    <circle cx="9" cy="8" r="3" />
    <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
    <path d="M16 5.5a3 3 0 0 1 0 5.5M17.5 14a5 5 0 0 1 3 5" />
  </svg>
);
