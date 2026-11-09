// Slim header for /proof: logo home, theme toggle, open the app. (The site header's links are
// in-page anchors for "/", so it is not reused here.) Own classes (pf-nav*), styled in proof.css.

import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export function ProofHeader() {
  return (
    <header className="pf-nav">
      <div className="pf-wrap pf-nav-row">
        <Link href="/" className="pf-nav-logo" aria-label="Baaki home">
          <Logo size={32} />
        </Link>
        <nav className="pf-nav-links" aria-label="Proof sections">
          <a href="#proof-bars">Conditions</a>
          <a href="#proof-clips">Every clip</a>
          <a href="#proof-method">Method</a>
        </nav>
        <div className="pf-nav-actions">
          <ThemeToggle />
          <Link href="/app" className="pf-pill pf-pill-ink">
            Open app
          </Link>
        </div>
      </div>
    </header>
  );
}
