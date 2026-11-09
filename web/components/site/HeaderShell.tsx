"use client";

// The floating site header: transparent over the hero sky, a solid hairline bar once the page scrolls.

import { useEffect, useState, type ReactNode } from "react";

export function HeaderShell({ children }: { children: ReactNode }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header className="s-header s-header-float" data-scrolled={scrolled}>
      {children}
    </header>
  );
}
