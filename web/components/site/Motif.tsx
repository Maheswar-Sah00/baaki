// Line drawings for the "What Baaki can do" canvases (shown until a photo is supplied): one quiet
// object per feature, drawn in the card's tone ink. Decorative only (aria-hidden).

const P = { fill: "none", stroke: "currentColor", strokeWidth: 2.4, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function Wage() {
  // a months calendar: two paid, three owed, one still to ask
  const cells = [
    [44, 84],
    [125, 84],
    [206, 84],
    [44, 150],
    [125, 150],
    [206, 150],
  ];
  return (
    <>
      <rect x="20" y="20" width="280" height="204" rx="24" {...P} />
      <path d="M20 66H300" {...P} />
      <rect x="78" y="8" width="10" height="26" rx="5" className="m-fill" {...P} />
      <rect x="232" y="8" width="10" height="26" rx="5" className="m-fill" {...P} />
      {cells.map(([x, y], i) => (
        <g key={i}>
          <rect x={x} y={y} width="70" height="52" rx="12" {...P} strokeDasharray={i === 5 ? "5 7" : undefined} />
          {i < 2 ? <path d={`M${x + 24} ${y + 27}l8 8l15-16`} {...P} /> : null}
          {i >= 2 && i < 5 ? (
            <text x={x + 35} y={y + 34} textAnchor="middle" fontSize="20" fontWeight="600" fill="currentColor">
              ₹
            </text>
          ) : null}
        </g>
      ))}
    </>
  );
}

function Letter() {
  return (
    <>
      <rect x="72" y="14" width="176" height="160" rx="12" className="m-fill" {...P} />
      <path d="M96 48H224M96 72H206M96 96H224M96 120H176" {...P} />
      <path d="M160 146c9-14 18 12 27 0s18-10 26 2" {...P} />
      <rect x="36" y="108" width="248" height="116" rx="16" className="m-fill" {...P} />
      <path d="M40 116L160 184L280 116" {...P} />
    </>
  );
}

function PromiseNote() {
  return (
    <>
      <rect x="48" y="16" width="224" height="208" rx="16" {...P} />
      {[52, 92, 132, 172].map((y) => (
        <circle key={y} cx="70" cy={y} r="5" {...P} />
      ))}
      <path d="M96 60H248M96 96H248M96 132H248M96 168H248M96 204H248" {...P} strokeOpacity="0.55" />
      <path d="M100 52c10-8 20 6 30-2s18 6 28 0M100 88c12-8 22 6 34-2" {...P} />
      <path d="M100 124h86M100 160h70" {...P} />
      <path d="M98 128l92-10M98 164l76-8" {...P} />
      <circle cx="226" cy="84" r="16" {...P} />
    </>
  );
}

function Evidence() {
  return (
    <>
      <rect x="22" y="34" width="210" height="62" rx="31" {...P} />
      <circle cx="54" cy="65" r="15" {...P} />
      <path d="M50 58v14l11-7z" fill="currentColor" stroke="none" />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((i) => {
        const h = 10 + ((i * 37) % 26);
        return <path key={i} d={`M${84 + i * 10} ${65 - h / 2}V${65 + h / 2}`} {...P} />;
      })}
      <rect x="104" y="122" width="190" height="52" rx="26" {...P} />
      <path d="M128 142H252M128 156H212" {...P} />
      <path d="M262 18v52l-13-10l-13 10V18z" className="m-fill" {...P} />
      <path d="M40 210H280" {...P} strokeDasharray="4 8" />
    </>
  );
}

function Raise() {
  return (
    <>
      <path d="M28 214H292" {...P} />
      <rect x="48" y="150" width="46" height="64" rx="9" {...P} />
      <rect x="110" y="124" width="46" height="90" rx="9" {...P} />
      <rect x="172" y="96" width="46" height="118" rx="9" {...P} />
      <rect x="234" y="60" width="46" height="154" rx="9" {...P} strokeDasharray="6 7" />
      <path d="M58 120C112 104 168 76 236 34" {...P} />
      <path d="M220 30l17 4l-5 16" {...P} />
    </>
  );
}

function Exit() {
  return (
    <>
      <path d="M24 222H300" {...P} />
      <path d="M64 222V96a68 68 0 0 1 136 0v126" {...P} />
      <path d="M94 222V104a38 38 0 0 1 76 0v118" {...P} />
      <circle cx="156" cy="168" r="4" fill="currentColor" stroke="none" />
      <rect x="218" y="112" width="84" height="84" rx="14" className="m-fill" {...P} />
      <path d="M218 138H302" {...P} />
      <circle cx="260" cy="168" r="14" {...P} />
    </>
  );
}

const MOTIFS = { wage: Wage, letter: Letter, promise: PromiseNote, evidence: Evidence, raise: Raise, exit: Exit } as const;
export type MotifKey = keyof typeof MOTIFS;

export function Motif({ name, className }: { name: MotifKey; className?: string }) {
  const Draw = MOTIFS[name];
  return (
    <svg className={className} viewBox="0 0 320 240" aria-hidden="true" focusable="false">
      <Draw />
    </svg>
  );
}
