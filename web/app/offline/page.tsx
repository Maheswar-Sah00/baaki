import type { Metadata } from "next";
import Link from "next/link";
import { LogoMark } from "@/components/ui/Logo";
import "@/components/pwa/offline.css";

export const metadata: Metadata = { title: "Offline", robots: { index: false } };

// Shown by the service worker when a page is requested with no connection and no cached copy.
// Server-only and dependency-light: it is precached, so it must render without the network.
export default function OfflinePage() {
  return (
    <main className="ofl">
      <div className="ofl-card">
        <div className="ofl-mark" aria-hidden="true">
          <LogoMark size={28} />
          <span className="ofl-signal">
            <i />
            <i />
            <i />
          </span>
        </div>
        <p className="ofl-kicker">Offline</p>
        <h1 className="ofl-title">
          No connection <em>right now.</em>
        </h1>
        <p className="ofl-sub">
          Baaki needs the internet to listen and to send. Nothing is lost: try again when you are back online.
        </p>
        <p className="ofl-langs">
          <span lang="te">ఇంటర్నెట్ లేదు. మళ్ళీ ప్రయత్నించండి.</span>
          <span lang="hi">इंटरनेट नहीं है। फिर से कोशिश करें।</span>
        </p>
        <Link href="/app" className="ofl-btn">
          Try again
        </Link>
        <p className="ofl-help">
          In danger? Call <a href="tel:112">112</a> or <a href="tel:181">181</a>.
        </p>
      </div>
    </main>
  );
}
