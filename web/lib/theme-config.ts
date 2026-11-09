// Theme constants and the pre-paint script. No "use client": app/layout.tsx (a server component)
// imports THEME_INIT_SCRIPT from here. Runtime helpers live in lib/theme.ts.

export type Theme = "light" | "dark";
export type Palette = "warm" | "gnani";

/** Change this one constant to switch the default palette for everyone. */
export const DEFAULT_PALETTE: Palette = "gnani";

export const THEME_KEY = "baaki-theme";
export const PALETTE_KEY = "baaki-palette";

/**
 * Runs in <head> before paint. Also captures `beforeinstallprompt` early (it can fire before React
 * mounts) into window.__baakiInstall for <InstallButton>.
 */
export const THEME_INIT_SCRIPT = `(function(){var d=document.documentElement,t=null,p=null;
try{var q=new URLSearchParams(location.search);t=q.get("theme");p=q.get("palette");
if(p==="warm"||p==="gnani"){sessionStorage.setItem("${PALETTE_KEY}",p)}else{p=sessionStorage.getItem("${PALETTE_KEY}")}
if(t!=="light"&&t!=="dark"){t=localStorage.getItem("${THEME_KEY}")}}catch(e){}
if(t!=="light"&&t!=="dark"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}
if(p!=="warm"&&p!=="gnani"){p="${DEFAULT_PALETTE}"}
d.setAttribute("data-theme",t);d.setAttribute("data-palette",p);
try{var m=document.querySelector('meta[name="theme-color"]');if(m){m.setAttribute("content",getComputedStyle(d).getPropertyValue("--meta-bg").trim()||(t==="dark"?"#0c111d":"#fcf7f2"))}}catch(e){}
window.__baakiInstall=null;
window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();window.__baakiInstall=e;window.dispatchEvent(new Event("baaki:installable"))});
window.addEventListener("appinstalled",function(){window.__baakiInstall=null;window.dispatchEvent(new Event("baaki:installable"))});
})();`;

