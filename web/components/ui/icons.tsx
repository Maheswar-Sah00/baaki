// Inline icons (stroke = currentColor, 1.8 hairline-ish weight). Replace freely; screens only use these names.

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

export const MicIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </svg>
);
export const StopIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />
  </svg>
);
export const PlayIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M8 5v14l11-7z" fill="currentColor" />
  </svg>
);
export const PauseIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M8 5v14M16 5v14" />
  </svg>
);
export const ShareIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14" />
  </svg>
);
export const PhoneIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z" />
  </svg>
);
export const CheckIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);
export const CrossIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);
export const BackIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M15 18l-6-6 6-6" />
  </svg>
);
export const ShieldIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);
export const FileIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6M8 13h8M8 17h5" />
  </svg>
);
export const HomeIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />
  </svg>
);
export const DiaryIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M5 4a2 2 0 0 1 2-2h12v18H7a2 2 0 0 0-2 2z" />
    <path d="M5 20V4M9 7h6M9 11h4" />
  </svg>
);
export const WaveIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M3 12h1M7 8v8M11 5v14M15 9v6M19 7v10M22 12h-1" />
  </svg>
);
export const SunIcon = ({ className }: P) => (
  <svg {...base} className={className} strokeWidth={1.8}>
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 2.8v2.2M12 19v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.8 12h2.2M19 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" />
  </svg>
);
export const MoonIcon = ({ className }: P) => (
  <svg {...base} className={className} strokeWidth={1.8}>
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />
  </svg>
);
export const DownloadIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 3v12M7 10l5 5 5-5M5 21h14" />
  </svg>
);
export const ArrowRightIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
export const SparkIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M19 17l.7 1.8 1.8.7-1.8.7L19 22l-.7-1.8-1.8-.7 1.8-.7z" />
  </svg>
);
export const LockIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <rect x="4" y="10" width="16" height="11" rx="2.5" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </svg>
);
export const RupeeIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M6 4h12M6 9h12M9 4c6 0 6 10 0 10H6l9 7" />
  </svg>
);
export const BotIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <rect x="4" y="8" width="16" height="12" rx="4" />
    <path d="M12 4v4M9 14h.01M15 14h.01" />
  </svg>
);
export const LanguageIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 5h9M8.5 3v2M6 5c0 4 3 7 6 8M11 5c0 4-3 8-7 9" />
    <path d="M13 21l4-9 4 9M14.5 18h5" />
  </svg>
);
export const BellIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" />
    <path d="M10 21h4" />
  </svg>
);
export const InboxIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 13.5 6.2 5.6A2 2 0 0 1 8.1 4h7.8a2 2 0 0 1 1.9 1.6L20 13.5V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
    <path d="M4 13.5h4.5l1.2 2h4.6l1.2-2H20" />
  </svg>
);
export const TrendUpIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M3 17l6-6 4 4 8-8" />
    <path d="M15 7h6v6" />
  </svg>
);
export const DoorIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M14 3H6a1 1 0 0 0-1 1v17h9" />
    <path d="M14 3l5 2v16l-5 0z" />
    <path d="M11.5 12.5h.01" />
  </svg>
);
export const ClockIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </svg>
);
export const ChevronRightIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M9 6l6 6-6 6" />
  </svg>
);
export const PenIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z" />
    <path d="M13.5 6.5l4 4" />
  </svg>
);
export const WalletIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <path d="M4 7a2 2 0 0 1 2-2h11v4" />
    <rect x="4" y="7" width="16" height="12" rx="2.5" />
    <path d="M16 13h.01" />
  </svg>
);
export const KeyboardIcon = ({ className }: P) => (
  <svg {...base} className={className}>
    <rect x="2.5" y="6" width="19" height="12" rx="2.5" />
    <path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M7 14h10" />
  </svg>
);
