"use client";

// "What Baaki can do": a numbered list (active = ink) and one large media card per feature. Each
// card is a photo slot (<AssetSlot>, prompts in docs/assets/site.md) with crisp live UI on top;
// until the photo exists (checked on the server, `photos`), a tinted canvas with a line drawing of
// the feature's object. Auto-advances; click or arrow keys select. Reduced motion: no auto-advance.
// Every figure is from the demo seed or the app's strings (synthetic names; estimates labelled).

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { prefersReducedMotion } from "@/lib/easing";
import { ArrowRightIcon, CheckIcon, FileIcon, PlayIcon } from "@/components/ui/icons";
import { Motif, type MotifKey } from "./Motif";

type Tone = "sky" | "lilac" | "peach" | "butter" | "sage" | "rose";
/** Where the illustration sits: "right" (chips in the left column), "left" (chips on the right, for
 *  art cut on its left edge) or "full" (cut on both sides: full width at the bottom, chips above). */
type Art = "right" | "left" | "full";
type Item = {
  key: MotifKey;
  title: string;
  slot: string;
  alt: string;
  tone: Tone;
  art: Art;
  /** The art is cut on its bottom edge, so it sits flush on the card's bottom edge. */
  bleed: boolean;
  caption: string;
  tryText: string;
  tryLang: string;
  href: string;
  /** Live UI chips: one stack at the top of the free column, one at its bottom. */
  top: ReactNode;
  bottom: ReactNode;
};

const ADVANCE_MS = 6000;

function Wave({ bars = 18 }: { bars?: number }) {
  return (
    <span className="cd-wave" aria-hidden="true">
      {Array.from({ length: bars }, (_, i) => (
        <i key={i} style={{ height: `${40 + ((i * 41) % 60)}%`, animationDelay: `${(i % 6) * 90}ms` }} />
      ))}
    </span>
  );
}

const ITEMS: Item[] = [
  {
    key: "wage",
    title: "Wage check",
    slot: "can-do-wage-check",
    alt: "Lakshmi speaks into her phone in a kitchen; calendars, a coin and a checklist around her",
    tone: "peach",
    art: "right",
    bleed: true,
    caption: "She says what she remembers. Baaki checks every month and every cut against Telangana’s minimum wage and the Code on Wages, and shows the source.",
    tryText: "Sharma garu moodu nelalu jeetham ivvaledu",
    tryLang: "Telugu",
    href: "/app",
    top: (
      <span className="cd-caption" lang="te">
        <span className="cd-live" /> శర్మ గారు మూడు నెలలు జీతం ఇవ్వలేదు…
      </span>
    ),
    bottom: (
      <>
        <span className="cd-chip">Code on Wages · s.20(2): ₹308 cut allowed, not ₹1,000</span>
        <span className="cd-money">
          <small>Baaki’s calculation</small>
          <b>₹12,692</b>
          <span className="cd-strike">
            She said <s>₹13,000</s>
          </span>
        </span>
      </>
    ),
  },
  {
    key: "letter",
    title: "Letter & voice note",
    slot: "can-do-letter-voice",
    alt: "Lakshmi’s phone sends a letter and a voice note to Sharma ji’s phone",
    tone: "sky",
    art: "full",
    bleed: true,
    caption: "A polite voice note in the employer’s language, opened with an AI disclosure, plus a Hindi or Telugu and English letter with the source for every number.",
    tryText: "Sharma ji ko Hindi mein bhejo",
    tryLang: "Hinglish",
    href: "/app",
    top: (
      <>
        <span className="cd-voice">
          <span className="cd-play">
            <PlayIcon />
          </span>
          <Wave />
          <small>0:21</small>
        </span>
        <span className="cd-chip">Hinglish · in Lakshmi’s voice · AI disclosure first</span>
      </>
    ),
    bottom: (
      <span className="cd-letter">
        <FileIcon />
        <span>
          <b>Letter to Sharma ji</b>
          <small>Hindi + English PDF · ₹12,692</small>
        </span>
      </span>
    ),
  },
  {
    key: "promise",
    title: "Promise keeper",
    slot: "can-do-promise-keeper",
    alt: "A ledger with ticks, a calendar with a ringed date, a milk can, a chit and coins",
    tone: "butter",
    art: "right",
    bleed: false,
    caption: "The chit money, the milk bill, the loan a relative swore to return. Every promise is saved with the date and their own words, and a polite reminder is ready when it slips.",
    tryText: "Srinivas agent ee vaaram chivariki istaanu annaru",
    tryLang: "Telugu",
    href: "/dues",
    top: (
      <span className="cd-promise">
        <small>Chit money · Srinivas agent</small>
        <b>₹40,000</b>
      </span>
    ),
    bottom: (
      <>
        <span className="cd-chip cd-chip-rose" lang="te">
          “ఈ వారం చివరికి” · broken
        </span>
        <span className="cd-chip cd-chip-rose cd-chip-more" lang="te">
          “ఈ వారం చివరికి” · broken
        </span>
        <span className="cd-chip">6 promises in 4 months · reminder ready</span>
      </>
    ),
  },
  {
    key: "evidence",
    title: "Evidence inbox",
    slot: "can-do-evidence-inbox",
    alt: "Her phone’s chat bubble is saved into a folder with a shield and a padlock",
    tone: "lilac",
    art: "left",
    bleed: true,
    caption: "Got a WhatsApp reply? Share the voice note to Baaki. She hears it in her language, and any promise in it is saved as proof with the date.",
    tryText: "agle hafte 12,692 de dungi",
    tryLang: "Hinglish",
    href: "/app",
    top: (
      <>
        <span className="cd-voice cd-voice-in">
          <span className="cd-play">
            <PlayIcon />
          </span>
          <Wave bars={12} />
          <small>0:06</small>
        </span>
        <span className="cd-caption">“agle hafte 12,692 de dungi”</span>
      </>
    ),
    bottom: (
      <span className="cd-saved">
        <CheckIcon />
        <span>
          <b>Promise saved: ₹12,692</b>
          <small>by Sun 22 Nov · proof kept</small>
        </span>
      </span>
    ),
  },
  {
    key: "raise",
    title: "Haq Raise",
    slot: "can-do-haq-raise",
    alt: "A worker and an employer shake hands over an agreement with a tick and rising bars",
    tone: "sage",
    art: "right",
    bleed: false,
    caption: "Paid on time but below the minimum? Baaki asks for a raise to the minimum wage, with a step-up plan the employer can live with. Part-time figures are estimates.",
    tryText: "Mehta madam se raise maangna hai",
    tryLang: "Hinglish",
    href: "/app",
    top: (
      <span className="cd-raise">
        <span>
          <small>Now</small>
          <b>₹2,500</b>
        </span>
        <ArrowRightIcon />
        <span>
          <small>Minimum (estimate)</small>
          <b>~₹4,000</b>
        </span>
      </span>
    ),
    bottom: (
      <span className="cd-money">
        <small>More every year</small>
        <b>₹18,000</b>
        <span className="cd-est">estimate · G.O.Ms.No.6</span>
      </span>
    ),
  },
  {
    key: "exit",
    title: "Exit kit",
    slot: "can-do-exit-kit",
    alt: "Lakshmi walks out through a gate holding a checklist",
    tone: "rose",
    art: "right",
    bleed: true,
    caption: "Told “don’t come from tomorrow”? Baaki shows the date her final dues fall due and her part-month pay, and makes the polite message. She presses Send.",
    tryText: "Kal se mat aana bola",
    tryLang: "Hinglish",
    href: "/app",
    top: (
      <span className="cd-promise">
        <small>Final dues should be paid within</small>
        <b>2 working days</b>
      </span>
    ),
    bottom: (
      <>
        <span className="cd-chip">Code on Wages · s.17(2)</span>
        <span className="cd-chip cd-chip-sage">
          <CheckIcon /> Part-month pay counted from her diary
        </span>
      </>
    ),
  },
];

export function CanDo({ photos = [] }: { photos?: string[] }) {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (paused || prefersReducedMotion()) return;
    const t = window.setTimeout(() => setActive((a) => (a + 1) % ITEMS.length), ADVANCE_MS);
    return () => window.clearTimeout(t);
  }, [active, paused]);

  // Phones: the tabs are one scrolling row; keep the active tab in view (scrolls the row only, never the page).
  useEffect(() => {
    const list = listRef.current;
    if (!list || list.scrollWidth <= list.clientWidth + 1) return;
    const tab = list.querySelectorAll<HTMLElement>(".cd-tab")[active];
    if (tab) list.scrollTo({ left: Math.max(0, tab.offsetLeft - 16), behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }, [active]);

  const item = ITEMS[active];
  const hasPhoto = photos.includes(item.slot);

  return (
    <div className="cd" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="cd-list" role="tablist" aria-label="What Baaki can do" ref={listRef}>
        {ITEMS.map((it, i) => (
          <button
            key={it.key}
            id={`cd-tab-${it.key}`}
            type="button"
            role="tab"
            aria-selected={i === active}
            aria-controls="cd-panel"
            tabIndex={i === active ? 0 : -1}
            className="cd-tab"
            onClick={() => setActive(i)}
            onKeyDown={(e) => {
              if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              e.preventDefault();
              const next = (i + (e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : ITEMS.length - 1)) % ITEMS.length;
              setActive(next);
              listRef.current?.querySelectorAll<HTMLButtonElement>(".cd-tab")[next]?.focus();
            }}
          >
            <span className="cd-num">{String(i + 1).padStart(2, "0")}</span>
            <span className="cd-name">{it.title}</span>
            {i === active && !paused ? <span key={active} className="cd-progress" style={{ animationDuration: `${ADVANCE_MS}ms` }} /> : null}
          </button>
        ))}
      </div>
      <div className="cd-panel" id="cd-panel" role="tabpanel" aria-labelledby={`cd-tab-${item.key}`}>
        <div className="cd-media" key={item.key} data-key={item.key} data-tone={item.tone} data-art={item.art} data-bleed={item.bleed}>
          {hasPhoto ? (
            <AssetSlot name={item.slot} alt={item.alt} ratio="16/10" tone={item.tone} rounded="var(--r-xl)" fit="contain" className="cd-art" />
          ) : (
            <div className="cd-canvas" aria-hidden="true">
              <Motif name={item.key} className="cd-motif" />
            </div>
          )}
          <div className="cd-overlays" aria-hidden="true">
            <div className="cd-stack cd-stack-top">{item.top}</div>
            <div className="cd-stack cd-stack-bottom">{item.bottom}</div>
          </div>
        </div>
        <p className="cd-caption-text">{item.caption}</p>
        <Link href={item.href} className="cd-try">
          <span className="cd-try-label">Try:</span>
          <span className="cd-try-text">“{item.tryText}”</span>
          <span className="cd-try-lang">{item.tryLang}</span>
          <ArrowRightIcon />
        </Link>
      </div>
    </div>
  );
}
