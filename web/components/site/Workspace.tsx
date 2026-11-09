"use client";

// The Baaki workspace window for the website (the Vyra "editor" analog): Baaki's agent log streams
// on the left, the real app plays in a phone in the centre with Sharma ji's case file filling in
// beside it, and a months ledger (one track per home) is filled in by a sweeping playhead at the
// bottom. Synthetic demo data that matches the app's seed (backend/app/seed.py, "today" = 9 Nov 2026):
// Lakshmi's three homes, Sharma ji owes ₹12,692. Every figure below is one the log itself says.
// Pure presentation, no API calls. Reduced motion: every line shown, ledger filled, playhead at today.

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { prefersReducedMotion } from "@/lib/easing";
import { BackIcon, CheckIcon, FileIcon, MicIcon, PlayIcon, SparkIcon } from "@/components/ui/icons";
import { PhoneDemo, type DemoScene } from "./PhoneDemo";

type Home = "sharma" | "reddy" | "mehta";
type Line = { at: number; text: string; scene: DemoScene; home?: Home; done?: boolean };

const LOOP_MS = 24000;
const LINES: Line[] = [
  { at: 300, text: "On it. Listening to your voice note in Telugu.", scene: "speak", home: "sharma" },
  { at: 2400, text: "Heard: Sharma ji, ₹4,000 a month, Aug to Oct not paid.", scene: "speak", home: "sharma" },
  { at: 4200, text: "Heard: ₹1,000 cut in July for 2 sick days.", scene: "speak", home: "sharma" },
  { at: 6400, text: "Read it all back to Lakshmi in Telugu. She said అవును.", scene: "confirm", home: "sharma", done: true },
  { at: 9800, text: "Checked the cut against s.20(2): ₹308, not ₹1,000.", scene: "knows", home: "sharma" },
  { at: 11600, text: "Baaki’s calculation for Sharma ji: ₹12,692.", scene: "knows", home: "sharma", done: true },
  { at: 13200, text: "Mehta madam pays ₹2,500. The minimum is about ₹4,000 (estimate).", scene: "knows", home: "mehta" },
  { at: 14800, text: "Reddy garu pays in full, every month. Fair employer.", scene: "knows", home: "reddy", done: true },
  { at: 16400, text: "Voice note ready for Sharma ji, in Hinglish. AI disclosure first.", scene: "send", home: "sharma" },
  { at: 18000, text: "Letter drafted: Hindi + English PDF.", scene: "send", home: "sharma", done: true },
  { at: 19600, text: "Waiting for Lakshmi to press Send.", scene: "send", home: "sharma" },
];

const MONTHS = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov"];
/** Where "today" (9 Nov) sits on the ruler, as a fraction of the six months. */
const TODAY = (5 + 9 / 30) / 6;

type Block = { m: number; span?: number; tone: "paid" | "short" | "unpaid" | "open"; label: string; short: string };
const TRACKS: { key: Home; name: string; meta: string; blocks: Block[] }[] = [
  {
    key: "sharma",
    name: "Sharma ji",
    meta: "Hinglish · ₹4,000",
    blocks: [
      { m: 0, tone: "paid", label: "Paid", short: "Paid" },
      { m: 1, tone: "short", label: "−₹1,000 cut", short: "Cut" },
      { m: 2, tone: "unpaid", label: "Not paid", short: "Due" },
      { m: 3, tone: "unpaid", label: "Not paid", short: "Due" },
      { m: 4, tone: "unpaid", label: "Not paid", short: "Due" },
      { m: 5, tone: "open", label: "Ask", short: "Ask" },
    ],
  },
  {
    key: "reddy",
    name: "Reddy garu",
    meta: "Telugu · ₹5,000",
    blocks: [0, 1, 2, 3, 4].map((m) => ({ m, tone: "paid" as const, label: "Paid", short: "Paid" })),
  },
  {
    key: "mehta",
    name: "Mehta madam",
    meta: "Hinglish · ₹2,500",
    blocks: [0, 1, 2, 3, 4].map((m) => ({ m, tone: "short" as const, label: "~₹1,500 short", short: "Short" })),
  },
];

/** The case file beside the phone: each row lands when the log line that states it appears. */
function CaseFile({ shown }: { shown: number }) {
  const has = (n: number) => shown >= n;
  const status = has(11) ? "Ready · she presses Send" : has(6) ? "Calculated" : has(4) ? "Confirmed" : "Listening";
  return (
    <div className="ws-case">
      <div className="ws-case-head">
        <span className="ws-case-k">Case file</span>
        <span className="ws-case-status" data-on={has(4) || undefined}>
          <i /> {status}
        </span>
      </div>
      <p className="ws-case-who">
        Sharma ji <small>· Hinglish</small>
      </p>
      <dl className="ws-case-facts">
        <div data-on={has(2) || undefined}>
          <dt>Wage</dt>
          <dd>₹4,000 / month</dd>
        </div>
        <div data-on={has(2) || undefined}>
          <dt>Not paid</dt>
          <dd>Aug – Oct</dd>
        </div>
        <div data-on={has(3) || undefined}>
          <dt>Sick-day cut</dt>
          <dd>
            {has(5) ? (
              <>
                <s>₹1,000</s> ₹308 allowed
              </>
            ) : (
              "₹1,000"
            )}
          </dd>
        </div>
        <div data-on={has(4) || undefined}>
          <dt>She confirmed</dt>
          <dd lang="te">
            అవును <CheckIcon />
          </dd>
        </div>
      </dl>
      <div className="ws-case-total" data-on={has(6) || undefined}>
        <span>Baaki’s calculation</span>
        <b>{has(6) ? "₹12,692" : "₹ —"}</b>
      </div>
      <div className="ws-case-out">
        <span className="ws-case-k">Ready to send</span>
        <span className="ws-case-item" data-on={has(9) || undefined}>
          <span className="ws-case-ic">
            <PlayIcon />
          </span>
          <span>
            Voice note <small>Hinglish · 0:21</small>
          </span>
        </span>
        <span className="ws-case-item" data-on={has(10) || undefined}>
          <span className="ws-case-ic">
            <FileIcon />
          </span>
          <span>
            Letter <small>Hindi + English PDF</small>
          </span>
        </span>
      </div>
    </div>
  );
}

export function Workspace() {
  const [cycle, setCycle] = useState(0);
  const [shown, setShown] = useState(0);
  const [still, setStill] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (prefersReducedMotion()) {
      const id = requestAnimationFrame(() => {
        setStill(true);
        setShown(LINES.length);
      });
      return () => cancelAnimationFrame(id);
    }
    const timers = LINES.map((l, i) => window.setTimeout(() => setShown(i + 1), l.at));
    const reset = window.setTimeout(() => {
      setShown(0);
      setCycle((c) => c + 1);
    }, LOOP_MS);
    return () => {
      timers.forEach((t) => window.clearTimeout(t));
      window.clearTimeout(reset);
    };
  }, [cycle]);

  // The log reads top-down like a chat; once it is full, the newest line scrolls into view.
  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    el.dataset.overflow = String(el.scrollHeight > el.clientHeight + 2);
    el.scrollTo({ top: el.scrollHeight, behavior: still ? "auto" : "smooth" });
  }, [shown, cycle, still]);

  const current = shown > 0 ? LINES[shown - 1] : null;
  const scene: DemoScene = still ? "knows" : current?.scene ?? "speak";
  const active: Home | undefined = still ? undefined : current?.home ?? "sharma";
  const waiting = shown === LINES.length;
  const checking = !still && shown < LINES.length - 2;

  return (
    <div className="ws" role="img" aria-label="The Baaki workspace: Baaki listens to Lakshmi in Telugu, reads it back, checks every month of pay in her three homes against the law, calculates ₹12,692 for Sharma ji, drafts a Hinglish voice note and a Hindi and English letter, and waits for her to press Send.">
      <div className="ws-top" aria-hidden="true">
        <span className="ws-back">
          <BackIcon /> <span>Back</span>
        </span>
        <b className="ws-title">Lakshmi’s dues</b>
        <span className="ws-tag">
          <i className="ws-dot" /> Baaki · తెలుగు <CheckIcon className="ws-tick" />
        </span>
        <span className="ws-grow" />
        <span className="ws-conn">
          <i className="ws-dot ws-dot-live" /> <span>Connected</span>
        </span>
        <span className="ws-send" data-waiting={waiting}>
          Send
        </span>
      </div>

      <div className="ws-body" aria-hidden="true">
        {/* ------------------------------------------------ agent log */}
        <div className="ws-side">
          <div className="ws-tabs">
            <span>Voice notes</span>
            <span className="ws-tab-on">Baaki</span>
          </div>
          <div className="ws-agent">
            <SparkIcon /> <b>Baaki</b>
            <span className="ws-grow" />
            <small>Telugu → Hinglish</small>
          </div>
          <div className="ws-log" key={cycle} ref={logRef}>
            <div className="ws-voice">
              <span className="ws-voice-play">
                <PlayIcon />
              </span>
              <span className="ws-voice-wave">
                {Array.from({ length: 22 }, (_, i) => (
                  <i key={i} style={{ "--h": `${36 + ((i * 37) % 64)}%` } as CSSProperties} />
                ))}
              </span>
              <small>0:21</small>
              <p lang="te">శర్మ గారు మూడు నెలలు జీతం ఇవ్వలేదు, నెలకు నాలుగు వేలు…</p>
            </div>
            {LINES.slice(0, shown).map((l, i) => (
              <p key={l.at} className="ws-line" data-last={i === shown - 1 && !still} data-done={l.done}>
                {l.text}
                {l.done ? <CheckIcon className="ws-line-tick" /> : null}
              </p>
            ))}
            {!waiting ? (
              <span className="ws-typing">
                <i />
                <i />
                <i />
              </span>
            ) : null}
          </div>
          <div className="ws-ask">
            <span className="ws-ask-plus">+</span>
            <span>Tap the mic and speak…</span>
            <span className="ws-ask-mic">
              <MicIcon />
            </span>
          </div>
        </div>

        {/* ------------------------------------------------ phone preview + case file */}
        <div className="ws-stage">
          <span className="ws-stage-label">Live preview · Lakshmi’s phone</span>
          <div className="ws-stage-row">
            <PhoneDemo scene={scene} className="ws-phone" />
            <CaseFile shown={shown} />
          </div>
        </div>
      </div>

      {/* ------------------------------------------------ months ledger */}
      <div className="ws-ledger" aria-hidden="true">
        <div className="ws-tools">
          <span className="ws-tools-group">
            <span>Homes</span>
            <span>Months</span>
            <span>Cuts</span>
            <span>Promises</span>
          </span>
          <span className="ws-tools-time">
            <PlayIcon className="ws-tools-play" />
            <b>Jun 2026</b>
            <span>| 9 Nov 2026</span>
          </span>
          <span className="ws-grow" />
          <span className="ws-status" data-checking={checking}>
            <i className="ws-dot" /> {checking ? "Baaki is checking" : waiting ? "Ready · she presses Send" : "Checked against G.O.Ms.No.6"}
          </span>
        </div>
        <div className="ws-grid" key={cycle} data-still={still} style={{ "--loop": `${LOOP_MS}ms`, "--today": TODAY } as CSSProperties}>
          <div className="ws-ruler">
            <span className="ws-label-col" />
            <span className="ws-months">
              {MONTHS.map((m) => (
                <span key={m}>{m}</span>
              ))}
            </span>
          </div>
          {TRACKS.map((t) => (
            <div key={t.key} className="ws-track" data-active={active === t.key}>
              <span className="ws-label-col">
                <b>{t.name}</b>
                <small>{t.meta}</small>
              </span>
              <span className="ws-lane">
                {t.blocks.map((b) => (
                  <span key={b.m} className="ws-block" data-tone={b.tone} style={{ "--m": b.m, "--span": b.span ?? 1 } as CSSProperties}>
                    {/* the cell is filled in as the playhead crosses it (a wipe, never a colour fade) */}
                    <span className="ws-block-fill">
                      <span className="ws-block-label">{b.label}</span>
                      <span className="ws-block-short">{b.short}</span>
                    </span>
                  </span>
                ))}
              </span>
            </div>
          ))}
          <span className="ws-ph-area">
            <span className="ws-playhead">
              <span className="ws-playhead-cap" />
            </span>
          </span>
        </div>
        <div className="ws-legend">
          <span data-tone="paid">Paid</span>
          <span data-tone="short">Short of the law</span>
          <span data-tone="unpaid">Not paid</span>
        </div>
      </div>
    </div>
  );
}
