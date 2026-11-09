// Baaki logo: the voice-bubble mark (CSS gradient tile, follows the palette) + wordmark.
// Server-safe (no hooks). The PNG app icons come from scripts/make-icons.mjs.

export function LogoMark({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <span className={`logo-mark ${className ?? ""}`} style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 512 512">
        <path className="logo-bubble" d="M150 112h212a76 76 0 0 1 76 76v108a76 76 0 0 1-76 76H218l-76 58 14-58h-6a76 76 0 0 1-76-76V188a76 76 0 0 1 76-76z" />
        <g className="logo-bars">
          <rect x="168" y="214" width="26" height="72" rx="13" />
          <rect x="214" y="180" width="26" height="140" rx="13" />
          <rect x="260" y="200" width="26" height="100" rx="13" />
          <rect x="306" y="226" width="26" height="48" rx="13" />
        </g>
        <circle className="logo-coin" cx="398" cy="128" r="62" />
        <path className="logo-rupee" d="M374 102h48M374 122h48M384 102c26 0 26 40 0 40h-10l34 30" />
      </svg>
    </span>
  );
}

export function Logo({ size = 36, className, telugu = true }: { size?: number; className?: string; telugu?: boolean }) {
  return (
    <span className={`logo ${className ?? ""}`}>
      <LogoMark size={size} />
      <span className="logo-word">
        Baaki
        {telugu ? (
          <span className="logo-te" lang="te">
            బాకీ
          </span>
        ) : null}
      </span>
    </span>
  );
}
