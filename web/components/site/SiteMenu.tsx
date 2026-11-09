"use client";

// Compact section menu for the site header below 1080px (where the floating nav pill does not fit):
// a round button that opens a small sheet of the same links. Escape, a tap outside or a link closes it.

import { useEffect, useRef, useState } from "react";

export function SiteMenu({ links }: { links: { href: string; label: string }[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    const onDown = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <div className="s-menu" ref={ref}>
      <button
        ref={btnRef}
        type="button"
        className="s-menu-btn"
        aria-expanded={open}
        aria-controls="s-menu-panel"
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="s-menu-icon" data-open={open} aria-hidden="true">
          <i />
          <i />
        </span>
      </button>
      {open ? (
        <nav id="s-menu-panel" className="s-menu-panel" aria-label="Sections">
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)}>
              {l.label}
            </a>
          ))}
        </nav>
      ) : null}
    </div>
  );
}
