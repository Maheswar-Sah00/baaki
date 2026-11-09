// Generates the PWA icons in public/icons from the Baaki mark (below) with sharp.
//   node scripts/make-icons.mjs
// The mark: a speech bubble holding the బాకీ wordmark, on the brand gradient, with a rupee coin
// and three voice bars. Telugu text is shaped by librsvg with "Nirmala UI" (Windows) or
// "Noto Sans Telugu"; the PNGs are committed, so other machines never need to run this.
import sharp from "sharp";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(OUT, { recursive: true });

const PALETTES = {
  warm: { a: "#f7a531", b: "#f47a3a", c: "#e2457a", ink: "#2a1206", paper: "#fffaf5", coin: "#2a1206", coinInk: "#ffc04d" },
  gnani: { a: "#fe914b", b: "#cf82a6", c: "#9f73f4", ink: "#101828", paper: "#ffffff", coin: "#101828", coinInk: "#fea76f" },
};
const P = PALETTES[process.env.PALETTE === "warm" ? "warm" : "gnani"]; // default: gnani (DEFAULT_PALETTE)

/** Content drawn on a 512 canvas; `scale` shrinks it about the centre (maskable safe zone). */
function mark({ scale = 1, rounded = true, text = true } = {}) {
  const t = `translate(256 256) scale(${scale}) translate(-256 -256)`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${P.a}"/><stop offset="0.5" stop-color="${P.b}"/><stop offset="1" stop-color="${P.c}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.25" cy="0.15" r="0.75">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.45"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" ${rounded ? 'rx="116"' : ""} fill="url(#g)"/>
  <rect width="512" height="512" ${rounded ? 'rx="116"' : ""} fill="url(#glow)"/>
  <g transform="${t}">
    <path fill="${P.paper}" d="M150 112h212a76 76 0 0 1 76 76v108a76 76 0 0 1-76 76H218l-76 58 14-58h-6a76 76 0 0 1-76-76V188a76 76 0 0 1 76-76z"/>
    ${
      text
        ? `<text x="258" y="292" font-family="Nirmala UI, Noto Sans Telugu, sans-serif" font-weight="700" font-size="128" text-anchor="middle" fill="${P.ink}" letter-spacing="-4">బాకీ</text>`
        : `<g fill="url(#g)"><rect x="168" y="214" width="26" height="72" rx="13"/><rect x="214" y="180" width="26" height="140" rx="13"/><rect x="260" y="200" width="26" height="100" rx="13"/><rect x="306" y="226" width="26" height="48" rx="13"/></g>`
    }
    <circle cx="398" cy="128" r="62" fill="${P.coin}"/>
    <circle cx="398" cy="128" r="62" fill="none" stroke="${P.paper}" stroke-width="10"/>
    <path fill="none" stroke="${P.coinInk}" stroke-width="11" stroke-linecap="round" stroke-linejoin="round" d="M374 102h48M374 122h48M384 102c26 0 26 40 0 40h-10l34 30"/>
    ${text ? `<g fill="${P.c}" opacity="0.9"><rect x="196" y="322" width="14" height="22" rx="7"/><rect x="220" y="316" width="14" height="34" rx="7"/><rect x="244" y="324" width="14" height="18" rx="7"/></g>` : ""}
  </g>
</svg>`;
}

const jobs = [
  ["icon-192.png", 192, mark()],
  ["icon-512.png", 512, mark()],
  ["apple-touch-icon.png", 180, mark({ rounded: false })],
  ["maskable-192.png", 192, mark({ scale: 0.78, rounded: false })],
  ["maskable-512.png", 512, mark({ scale: 0.78, rounded: false })],
];
for (const [name, size, svg] of jobs) {
  await sharp(Buffer.from(svg)).resize(size, size).png().toFile(path.join(OUT, name));
  console.log("wrote", name);
}
// Source SVGs: logo.svg (with the wordmark) and favicon.svg (text-free, so it renders anywhere).
writeFileSync(path.join(OUT, "logo.svg"), mark());
writeFileSync(path.join(OUT, "favicon.svg"), mark({ text: false }));
console.log("wrote logo.svg, favicon.svg");
