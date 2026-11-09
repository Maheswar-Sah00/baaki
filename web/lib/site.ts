// Public origin of the web app, used as metadataBase for link previews (og:image needs an absolute URL).
// Set NEXT_PUBLIC_SITE_URL to the public HTTPS origin when the app is shared; local demos use :3020.
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3020").trim().replace(/\/+$/, "");

/** Default preview image: the logo and the tagline only (no names, no amounts). */
export const OG_IMAGE = { url: "/og/baaki-og.png", width: 1200, height: 630, alt: "Baaki: say what you are owed" };
