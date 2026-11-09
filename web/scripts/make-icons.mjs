// Generates the PWA icons in public/icons from the Baaki mark with sharp.
//   node scripts/make-icons.mjs
// The mark (10 Nov 2026): a speech bubble drawn as a "b" (round stem and bowl, tail at the bottom
// right, a coin-round counter). Flat and single colour, the same path as components/ui/Logo.tsx.
// Colours are the `pale` palette (app/theme-pale.css): ink #0e0e0c, paper #fbfaf7.
//
//   icon-192/512.png        paper mark on an ink squircle (reads on any launcher or wallpaper)
//   maskable-192/512.png    full-bleed ink square, mark well inside the 80% safe circle
//   apple-touch-icon.png    full-bleed ink square (iOS rounds the corners itself)
//   favicon.svg             the bare mark, ink in light / white in dark (prefers-color-scheme)
//   logo.svg                the ink app tile as a vector (press kits, decks)
//   mark.svg                the bare ink mark on transparent
import sharp from "sharp";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(OUT, { recursive: true });

const INK = "#0e0e0c";
const PAPER = "#fbfaf7";
const WHITE = "#f5f5f3"; // dark-theme --text

// Keep in sync with MARK_PATH / MARK_VIEWBOX in components/ui/Logo.tsx.
const MARK_PATH =
  "M80 120a64 64 0 0 1 128 0V170a160 160 0 0 1 248 134V480L400 432H144a64 64 0 0 1-64-64Z M296 246a58 58 0 1 0 0.01 0Z";
const MARK_BOX = { x: 56, y: 56, size: 424 }; // tight square around the mark

/** The mark scaled so its box is `frac` of a 512 canvas, centred. */
function placed(frac, fill) {
  const s = (512 * frac) / MARK_BOX.size;
  const off = (512 - MARK_BOX.size * s) / 2;
  const tx = off - MARK_BOX.x * s;
  const ty = off - MARK_BOX.y * s;
  return `<path fill="${fill}" transform="translate(${tx.toFixed(2)} ${ty.toFixed(2)}) scale(${s.toFixed(4)})" d="${MARK_PATH}"/>`;
}

function tile({ rounded, frac }) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" ${rounded ? 'rx="114"' : ""} fill="${INK}"/>
  ${placed(frac, PAPER)}
</svg>`;
}

const jobs = [
  ["icon-192.png", 192, tile({ rounded: true, frac: 0.56 })],
  ["icon-512.png", 512, tile({ rounded: true, frac: 0.56 })],
  ["apple-touch-icon.png", 180, tile({ rounded: false, frac: 0.56 })],
  // maskable: launchers crop to (at least) a centred circle of 80% diameter; a 50% mark box sits inside it
  ["maskable-192.png", 192, tile({ rounded: false, frac: 0.5 })],
  ["maskable-512.png", 512, tile({ rounded: false, frac: 0.5 })],
];
for (const [name, size, svg] of jobs) {
  await sharp(Buffer.from(svg)).resize(size, size).png({ compressionLevel: 9 }).toFile(path.join(OUT, name));
  console.log("wrote", name);
}

const box = `${MARK_BOX.x} ${MARK_BOX.y} ${MARK_BOX.size} ${MARK_BOX.size}`;
const favicon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}">
  <style>path{fill:${INK}}@media (prefers-color-scheme:dark){path{fill:${WHITE}}}</style>
  <path d="${MARK_PATH}"/>
</svg>
`;
const markSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}"><path fill="${INK}" d="${MARK_PATH}"/></svg>
`;
writeFileSync(path.join(OUT, "favicon.svg"), favicon);
writeFileSync(path.join(OUT, "mark.svg"), markSvg);
writeFileSync(path.join(OUT, "logo.svg"), tile({ rounded: true, frac: 0.56 }) + "\n");
console.log("wrote favicon.svg, mark.svg, logo.svg");
