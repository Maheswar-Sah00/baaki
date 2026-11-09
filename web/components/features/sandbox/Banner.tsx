import { SANDBOX_BANNER } from "@/lib/features/sandbox";

export const box: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--line)",
  borderRadius: "var(--r-lg, 16px)",
  padding: 16,
};

export const btn: React.CSSProperties = {
  minHeight: "var(--tap-min, 44px)",
  padding: "10px 18px",
  borderRadius: "var(--r-pill, 999px)",
  border: "none",
  background: "var(--accent)",
  color: "var(--accent-ink)",
  fontWeight: 600,
  fontSize: 16,
  cursor: "pointer",
};

/** Shown on every sandbox screen. */
export function Banner() {
  return (
    <div
      role="note"
      style={{
        background: "var(--warn-soft)",
        color: "var(--text)",
        border: "1px solid var(--warn)",
        borderRadius: "var(--r-md, 12px)",
        padding: "8px 12px",
        fontWeight: 600,
        fontSize: 14,
      }}
    >
      {SANDBOX_BANNER}
    </div>
  );
}
