// Slim header for /proof: logo home, theme toggle, open the app. (The site header's links are
// in-page anchors for "/", so it is not reused here.)

import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export function ProofHeader() {
  return (
    <header className="s-header">
      <div className="s-wrap s-header-row">
        <Link href="/" className="s-logo-link" aria-label="Baaki home">
          <Logo size={34} />
        </Link>
        <div className="s-header-actions">
          <ThemeToggle />
          <Link href="/app" className="btn btn-primary s-header-cta">
            Open app
          </Link>
        </div>
      </div>
    </header>
  );
}
