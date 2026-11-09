// Generates the default link-preview image public/og/baaki-og.png (1200x630) from the Baaki logo with sharp.
//   node scripts/make-og.mjs
// Generic on purpose: no names and no amounts, so it is safe for every route (including /e/{token}).
// Telugu text is shaped by librsvg with "Nirmala UI" (Windows) or "Noto Sans Telugu"; the PNG is committed.
import sharp from "sharp";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(WEB, "public", "og");
mkdirSync(OUT, { recursive: true });

const W = 1200;
const H = 630;
const LOGO = 280;
const logo = await sharp(readFileSync(path.join(WEB, "public", "icons", "logo.svg")))
  .resize(LOGO, LOGO)
  .png()
  .toBuffer();

const bg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="haze" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fff4ea"/><stop offset="0.55" stop-color="#fcf7f2"/><stop offset="1" stop-color="#f1eafe"/>
    </linearGradient>
    <linearGradient id="brand" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fe914b"/><stop offset="0.5" stop-color="#cf82a6"/><stop offset="1" stop-color="#9f73f4"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.2" cy="0.3" r="0.6">
      <stop offset="0" stop-color="#fe914b" stop-opacity="0.22"/><stop offset="1" stop-color="#fe914b" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#haze)"/>
  <rect width="${W}" height="${H}" fill="url(#glow)"/>
  <rect x="0" y="${H - 14}" width="${W}" height="14" fill="url(#brand)"/>
  <text x="450" y="270" font-family="Georgia, 'Instrument Serif', serif" font-size="112" fill="#101828">Baaki</text>
  <text x="450" y="350" font-family="Nirmala UI, Noto Sans Telugu, sans-serif" font-weight="700" font-size="54" fill="#9f73f4">బాకీ · money still owed</text>
  <text x="450" y="430" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="31" fill="#344054">Say what you are owed, in Telugu or Hinglish.</text>
  <text x="450" y="478" font-family="Segoe UI, Inter, Arial, sans-serif" font-size="31" fill="#344054">Baaki works out the money and speaks for you.</text>
</svg>`;

await sharp(Buffer.from(bg))
  .composite([{ input: logo, left: 110, top: Math.round((H - LOGO) / 2) - 10 }])
  .png({ compressionLevel: 9 })
  .toFile(path.join(OUT, "baaki-og.png"));
console.log("wrote public/og/baaki-og.png");
