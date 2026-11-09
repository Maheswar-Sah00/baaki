"use client";

// A live-looking Baaki phone for the website: a CSS phone frame whose screen plays the real flow on
// a loop (speak -> read-back -> voice note to the employer -> "Paisa aa gaya!"). Pure presentation
// with fictional demo data; no API calls. Reduced motion: no auto-advance, the dots switch scenes.

import { useEffect, useState, type CSSProperties } from "react";
import { createCounter } from "@/lib/counter";
import { inrWhole } from "@/lib/format";
import { prefersReducedMotion } from "@/lib/easing";
import { Confetti, StatusPill, Waveform } from "@/components/ui/kit";
import { Illustration } from "@/components/ui/Illustration";
import { CheckIcon, CrossIcon, MicIcon, PlayIcon, ShieldIcon } from "@/components/ui/icons";
import { LogoMark } from "@/components/ui/Logo";

export type DemoScene = "speak" | "confirm" | "send" | "paid";
const SCENES: { key: DemoScene; label: string; ms: number }[] = [
  { key: "speak", label: "Speak", ms: 6200 },
  { key: "confirm", label: "Confirm", ms: 3800 },
  { key: "send", label: "Send", ms: 4200 },
  { key: "paid", label: "Paid", ms: 4000 },
];

const STEPS = [4000, 8000, 12000, 13000];
const TRANSCRIPT = "మూడు నెలలు జీతం ఇవ్వలేదు… నెలకు నాలుగు వేలు… జ్వరం రోజులకి వెయ్యి కట్ చేశారు.";
const GLOSS = "“Three months not paid… four thousand a month… they cut a thousand for my fever days.”";
const CHIPS = [
  { label: "Monthly wage", value: "₹4,000", at: 1 },
  { label: "Months unpaid", value: "3", at: 3 },
  { label: "Sick-day cut", value: "₹1,000", at: 4 },
];

export function PhoneDemo({ scene: fixed, className, autoplay = true }: { scene?: DemoScene; className?: string; autoplay?: boolean }) {
  const [index, setIndex] = useState(0);
  const [cycle, setCycle] = useState(0);
  const scene = fixed ?? SCENES[index].key;

  useEffect(() => {
    if (fixed || !autoplay || prefersReducedMotion()) return;
    const timer = window.setTimeout(() => {
      setIndex((i) => {
        const next = (i + 1) % SCENES.length;
        if (next === 0) setCycle((c) => c + 1);
        return next;
      });
    }, SCENES[index].ms);
    return () => window.clearTimeout(timer);
  }, [index, fixed, autoplay]);

  return (
    <div className={`phone-demo ${className ?? ""}`}>
      <div className="phone" role="img" aria-label="The Baaki app: Lakshmi speaks in Telugu, the meter adds up ₹13,000, her employer gets a voice note and pays.">
        <span className="phone-btn phone-btn-1" aria-hidden="true" />
        <span className="phone-btn phone-btn-2" aria-hidden="true" />
        <div className="phone-screen" data-scene={scene}>
          <span className="phone-island" aria-hidden="true" />
          <div className="phone-status" aria-hidden="true">
            <span>9:41</span>
            <span className="phone-status-icons">
              <i />
              <i />
              <i />
            </span>
          </div>
          <div className="phone-app" key={`${scene}-${cycle}`} aria-hidden="true">
            {scene === "speak" ? <SpeakScene /> : null}
            {scene === "confirm" ? <ConfirmScene /> : null}
            {scene === "send" ? <SendScene /> : null}
            {scene === "paid" ? <PaidScene /> : null}
          </div>
        </div>
      </div>
      {!fixed ? (
        <div className="phone-dots" role="tablist" aria-label="Demo steps">
          {SCENES.map((s, i) => (
            <button
              key={s.key}
              type="button"
              role="tab"
              aria-selected={i === index}
              className="phone-dot"
              onClick={() => setIndex(i)}
              style={{ "--ms": `${s.ms}ms` } as CSSProperties}
            >
              <span className="phone-dot-bar" />
              <span className="phone-dot-label">{s.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MiniBar({ title }: { title: string }) {
  return (
    <div className="mini-bar">
      <LogoMark size={22} />
      <span>{title}</span>
      <ShieldIcon className="mini-bar-shield" />
    </div>
  );
}

function SpeakScene() {
  const [value, setValue] = useState(0);
  const [step, setStep] = useState(0);
  const [typed, setTyped] = useState(0);
  useEffect(() => {
    const still = prefersReducedMotion();
    if (still) {
      const id = requestAnimationFrame(() => {
        setValue(13000);
        setStep(4);
        setTyped(TRANSCRIPT.length);
      });
      return () => cancelAnimationFrame(id);
    }
    const counter = createCounter({ onFrame: setValue, onStep: (_v, i) => setStep(i + 1), onIdle: () => {}, onBusy: () => {} }, { holdMs: 260 });
    const t1 = window.setTimeout(() => counter.animateTo(STEPS, 13000), 700);
    let n = 0;
    const typer = window.setInterval(() => {
      n += 2;
      setTyped(Math.min(n, TRANSCRIPT.length));
      if (n >= TRANSCRIPT.length) window.clearInterval(typer);
    }, 55);
    return () => {
      window.clearTimeout(t1);
      window.clearInterval(typer);
      counter.dispose();
    };
  }, []);

  return (
    <>
      <MiniBar title="Tell Baaki" />
      <StatusPill tone="live">Listening · తెలుగు</StatusPill>
      <p className="mini-transcript" lang="te">
        {TRANSCRIPT.slice(0, typed)}
        <span className="mini-caret" />
      </p>
      <p className="mini-gloss">{GLOSS}</p>
      <div className="mini-meter">
        <span className="mini-meter-label">Baaki · money still owed</span>
        <span key={step} className="mini-meter-glow" />
        <span className="mini-meter-value">{inrWhole(value)}</span>
      </div>
      <div className="mini-chips">
        {CHIPS.filter((c) => step >= c.at).map((c) => (
          <span key={c.label} className="mini-chip">
            <small>{c.label}</small>
            <b>{c.value}</b>
          </span>
        ))}
      </div>
      <div className="mini-mic-row">
        <span className="mini-mic">
          <span className="mic-halo" />
          <span className="mic-halo mic-halo-2" />
          <span className="mini-mic-btn">
            <MicIcon />
          </span>
        </span>
        <Waveform active bars={16} level={0.8} className="mini-wave" />
      </div>
    </>
  );
}

function ConfirmScene() {
  return (
    <>
      <MiniBar title="Is this right?" />
      <div className="mini-card mini-readback">
        <span className="mini-kicker">Baaki reads it back</span>
        <p lang="te">మూడు నెలలు… నెలకు ₹4,000… జ్వరం కట్ ₹1,000… మొత్తం ₹13,000. సరేనా?</p>
        <span className="mini-play">
          <span className="mini-play-icon">
            <PlayIcon />
          </span>
          <Waveform active bars={14} level={0.7} className="mini-wave-sm" />
          <small>0:07</small>
        </span>
      </div>
      <dl className="mini-facts">
        <div>
          <dt>Employer</dt>
          <dd>Sharma ji</dd>
        </div>
        <div>
          <dt>Months</dt>
          <dd>Aug – Oct</dd>
        </div>
        <div>
          <dt>Wage</dt>
          <dd>₹4,000 / mo</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd className="grad-text">₹13,000</dd>
        </div>
      </dl>
      <div className="mini-yes-no">
        <span className="mini-btn mini-btn-yes">
          <CheckIcon /> అవును · Yes
        </span>
        <span className="mini-btn mini-btn-no">
          <CrossIcon /> Fix
        </span>
      </div>
    </>
  );
}

function SendScene() {
  return (
    <>
      <MiniBar title="Sharma ji" />
      <div className="mini-chat">
        <span className="mini-bubble mini-bubble-in">
          <span className="mini-play-icon">
            <PlayIcon />
          </span>
          <Waveform active bars={18} level={0.75} className="mini-wave-sm" />
          <small>0:21</small>
        </span>
        <span className="mini-bubble-meta">
          <StatusPill tone="accent" dot={false}>
            Hinglish · in Lakshmi’s voice
          </StatusPill>
        </span>
        <span className="mini-disclosure">“Yeh sandesh Lakshmi ki anumati se, unki awaaz mein, Baaki app ne banaya hai…”</span>
      </div>
      <div className="mini-card mini-bill">
        <span className="mini-kicker">Baaki for Lakshmi</span>
        <p>
          <span>Aug – Oct wages</span>
          <b>₹12,000</b>
        </p>
        <p>
          <span>Sick-day cut returned</span>
          <b>₹1,000</b>
        </p>
        <p className="mini-bill-total">
          <span>Total</span>
          <b>₹13,000</b>
        </p>
      </div>
      <span className="mini-btn mini-btn-grad">Pay ₹13,000 by UPI</span>
      <span className="mini-sub">or pay in 2 parts · ask a question</span>
    </>
  );
}

function PaidScene() {
  return (
    <>
      <Confetti pieces={22} />
      <div className="mini-paid">
        <Illustration name="celebrate" animated size={170} />
        <p className="mini-paid-title" lang="hi">
          Paisa aa gaya!
        </p>
        <p className="mini-paid-amount">₹13,000</p>
        <StatusPill tone="success">From Sharma ji · UPI</StatusPill>
      </div>
    </>
  );
}
