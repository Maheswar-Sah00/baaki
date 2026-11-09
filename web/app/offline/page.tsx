import type { Metadata } from "next";
import Link from "next/link";
import { Illustration } from "@/components/ui/Illustration";

export const metadata: Metadata = { title: "Offline", robots: { index: false } };

// Shown by the service worker when a page is requested with no connection and no cached copy.
export default function OfflinePage() {
  return (
    <main className="offline">
      <div className="offline-card">
        <Illustration name="empty" size={220} />
        <h1>No connection right now</h1>
        <p className="muted">
          Baaki needs the internet to listen and to send. Nothing is lost: try again when you are back online.
          <br />
          <span lang="te">ఇంటర్నెట్ లేదు. మళ్ళీ ప్రయత్నించండి.</span> · <span lang="hi">इंटरनेट नहीं है। फिर से कोशिश करें।</span>
        </p>
        <Link href="/app" className="btn btn-primary btn-big">
          Try again
        </Link>
        <p className="hint">
          In danger? Call <a href="tel:112">112</a> or <a href="tel:181">181</a>.
        </p>
      </div>
    </main>
  );
}
