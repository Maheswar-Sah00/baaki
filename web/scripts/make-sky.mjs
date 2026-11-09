// Renders the website hero sky (public/sky.webp): a pale, painterly sky with soft cream and peach
// clouds, drawn from SVG fractal noise and rasterised with sharp. Original artwork, no stock image.
//   node scripts/make-sky.mjs
import sharp from "sharp";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, "..", "public", "sky.webp");
const W = 2400;
const H = 1500;

// One cloud layer: noise -> alpha with a soft threshold; a peach-grey underside offset below a
// cream/white top gives the painted, lit-from-above look.
const cloud = (id, seed, fx, fy, oct, slope, cut, top, under, blur, dy) => `
  <filter id="${id}" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="${fx} ${fy}" numOctaves="${oct}" seed="${seed}" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  ${slope} 0 0 0 ${cut}" result="a"/>
    <feGaussianBlur in="a" stdDeviation="${blur}" result="b"/>
    <feOffset in="b" dy="${dy}" result="bo"/>
    <feFlood flood-color="${under}"/>
    <feComposite in2="bo" operator="in" result="under"/>
    <feOffset in="b" dy="${-dy * 0.6}" result="bt"/>
    <feFlood flood-color="${top}"/>
    <feComposite in2="bt" operator="in" result="top"/>
    <feMerge><feMergeNode in="under"/><feMergeNode in="top"/></feMerge>
  </filter>`;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#a7c3e8"/>
      <stop offset="0.4" stop-color="#c3d6ef"/>
      <stop offset="0.74" stop-color="#e6e7ef"/>
      <stop offset="1" stop-color="#fbfaf7"/>
    </linearGradient>
    <radialGradient id="veil" cx="0.5" cy="0.42" r="0.5">
      <stop offset="0" stop-color="#fbfaf7" stop-opacity="0.42"/>
      <stop offset="0.55" stop-color="#fbfaf7" stop-opacity="0.12"/>
      <stop offset="1" stop-color="#fbfaf7" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0.62" stop-color="#fbfaf7" stop-opacity="0"/>
      <stop offset="1" stop-color="#fbfaf7" stop-opacity="1"/>
    </linearGradient>
    <linearGradient id="peachwash" x1="0" y1="0" x2="1" y2="0.4">
      <stop offset="0" stop-color="#f6d9c4" stop-opacity="0.55"/>
      <stop offset="0.5" stop-color="#f6d9c4" stop-opacity="0"/>
      <stop offset="1" stop-color="#ead9f2" stop-opacity="0.5"/>
    </linearGradient>
    ${cloud("c1", 7, 0.0012, 0.0026, 5, 3.4, -1.75, "#fdf6ee", "#e3cfc6", 5, 22)}
    ${cloud("c2", 19, 0.0017, 0.0036, 5, 4.0, -2.15, "#ffffff", "#dccfd6", 2.5, 14)}
    ${cloud("c3", 31, 0.0008, 0.0019, 4, 2.8, -1.45, "#f6e4d6", "#d9c3bd", 9, 30)}
    ${cloud("c4", 43, 0.0024, 0.005, 6, 4.6, -2.7, "#ffffff", "#e8dde2", 1.2, 8)}
  </defs>
  <rect width="100%" height="100%" fill="url(#sky)"/>
  <rect width="100%" height="100%" fill="url(#peachwash)"/>
  <rect width="100%" height="100%" filter="url(#c3)" opacity="0.75"/>
  <rect width="100%" height="100%" filter="url(#c1)" opacity="0.95"/>
  <rect width="100%" height="100%" filter="url(#c2)" opacity="0.9"/>
  <rect width="100%" height="100%" filter="url(#c4)" opacity="0.7"/>
  <rect width="100%" height="100%" fill="url(#veil)"/>
  <rect width="100%" height="100%" fill="url(#fade)"/>
</svg>`;

await sharp(Buffer.from(svg)).webp({ quality: 82, effort: 6 }).toFile(out);
console.log("wrote", out);
