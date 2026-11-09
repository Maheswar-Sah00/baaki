"use client";

// Fair Pay Check (V01): an employer answers four quick questions (or says them, "Bolo") and sees the
// G.O.Ms.No.6 Hyderabad Zone-I minimum, the gap and the cost per working day. Information, not
// accusation. Nothing is stored server-side; only the UI language is remembered in this browser.

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppBar, Confetti, GradientButton, StatusPill, ThemeToggle, Waveform } from "@/components/ui/primitives";
import { CheckIcon, MicIcon, ShareIcon, StopIcon } from "@/components/ui/icons";
import { Logo } from "@/components/ui/Logo";
import { inr, inrWhole } from "@/lib/format";
import { useRecorder, type Recording } from "@/lib/recorder";
import { shareMessage } from "@/lib/share";
import {
  CheckError,
  googleCalendarUrl,
  icsFile,
  runCheck,
  speakCheck,
  speakQuota,
  type CheckResult,
  type WorkType,
} from "@/lib/features/check";

import { BothGlyph, BroomGlyph, CalendarGlyph, CareGlyph, HeartGlyph, PotGlyph, UsersGlyph } from "./glyphs";
import { LANG_OPTIONS, makeT, type CheckLang, type CheckT } from "./strings";
import { useCountTo } from "./useCountTo";
import "./check.css";

const LANG_KEY = "baaki-check-lang";
const WORK: { id: WorkType; Icon: (p: { className?: string }) => React.JSX.Element }[] = [
  { id: "maid", Icon: BroomGlyph },
  { id: "cooking", Icon: PotGlyph },
  { id: "both", Icon: BothGlyph },
  { id: "care", Icon: CareGlyph },
];
const HOUR_CHIPS = [1, 2, 3, 4, 6, 8];
const DAYS = [1, 2, 3, 4, 5, 6, 7];

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
const digits = (v: string) => v.replace(/[^\d]/g, "").slice(0, 6);
const grouped = (v: string) => (v ? new Intl.NumberFormat("en-IN").format(Number(v)) : "");

function readLang(): CheckLang {
  try {
    const v = window.localStorage.getItem(LANG_KEY);
    if (v === "en" || v === "hi-en" || v === "te") return v;
  } catch {
    /* storage blocked */
  }
  return "en";
}

type Status = { kind: "idle" } | { kind: "loading" } | { kind: "done"; result: CheckResult } | { kind: "error" };
type Voice =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "heard"; transcript: string; missing: string[] }
  | { kind: "rest" };

export function FairPayCheck() {
  const [lang, setLang] = useState<CheckLang>("en");
  const t = useMemo(() => makeT(lang), [lang]);
  const htmlLang = LANG_OPTIONS.find((l) => l.id === lang)?.htmlLang ?? "en";

  useEffect(() => {
    const saved = readLang();
    if (saved !== "en") {
      const id = requestAnimationFrame(() => setLang(saved));
      return () => cancelAnimationFrame(id);
    }
  }, []);
  const chooseLang = (l: CheckLang) => {
    setLang(l);
    try {
      window.localStorage.setItem(LANG_KEY, l);
    } catch {
      /* fine */
    }
  };

  // ---------------------------------------------------------------- answers
  const [work, setWork] = useState<WorkType | null>(null);
  const [hours, setHours] = useState<number | null>(null);
  const [days, setDays] = useState<number>(6);
  const [pay, setPay] = useState("");
  const complete = work !== null && hours !== null && pay !== "";

  // Optional prefill from the URL (?w=maid&h=2&d=6&p=2500), read in the browser only: demo links.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const w = q.get("w");
    const h = Number(q.get("h"));
    const d = Number(q.get("d"));
    const p = digits(q.get("p") ?? "");
    const id = requestAnimationFrame(() => {
      if (w === "maid" || w === "cooking" || w === "both" || w === "care") setWork(w);
      if (h > 0 && h <= 16) setHours(Math.round(h * 2) / 2);
      if (d >= 1 && d <= 7) setDays(Math.round(d));
      if (p) setPay(p);
    });
    return () => cancelAnimationFrame(id);
  }, []);

  // ---------------------------------------------------------------- the check (debounced, abortable)
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!complete) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      setStatus((prev) => (prev.kind === "done" ? prev : { kind: "loading" }));
      runCheck({ work_type: work, hours_per_day: hours, days_per_week: days, monthly_pay: Number(pay) }, ctrl.signal)
        .then((result) => setStatus({ kind: "done", result }))
        .catch((e: unknown) => {
          if (e instanceof DOMException && e.name === "AbortError") return;
          setStatus({ kind: "error" });
        });
    }, 220);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [complete, work, hours, days, pay, attempt]);

  // Bring the result into view the first time it appears (phones).
  const resultRef = useRef<HTMLElement>(null);
  const scrolled = useRef(false);
  const hasResult = status.kind === "done";
  useEffect(() => {
    if (hasResult && !scrolled.current && resultRef.current) {
      scrolled.current = true;
      const r = resultRef.current.getBoundingClientRect();
      if (r.top > window.innerHeight * 0.6) resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [hasResult]);

  // ---------------------------------------------------------------- Bolo (voice)
  const [tries, setTries] = useState(0);
  const [voice, setVoice] = useState<Voice>({ kind: "idle" });
  useEffect(() => {
    let alive = true;
    void speakQuota().then((n) => alive && setTries(n));
    return () => {
      alive = false;
    };
  }, []);

  const workRef = useRef(work);
  useEffect(() => {
    workRef.current = work;
  }, [work]);

  const onRecorded = useCallback(async (rec: Recording) => {
    setVoice({ kind: "working" });
    try {
      const out = await speakCheck(rec.blob, rec.filename, workRef.current);
      const p = out.parsed;
      if (p.work_type) setWork(p.work_type);
      if (p.hours_per_day != null) setHours(p.hours_per_day);
      if (p.days_per_week != null) setDays(p.days_per_week);
      if (p.monthly_pay != null) setPay(String(Math.round(p.monthly_pay)));
      setTries(out.remaining_today);
      setVoice({ kind: "heard", transcript: out.transcript, missing: p.missing });
    } catch (e) {
      const err = e instanceof CheckError ? e : null;
      if (err?.status === 429) setTries(0);
      setVoice({ kind: "rest" });
    }
  }, []);
  const rec = useRecorder({ onRecorded, maxMs: 15_000 });
  const recording = rec.state === "recording";
  const micUsable = tries > 0 && voice.kind !== "working";

  // ---------------------------------------------------------------- next steps
  const [toast, setToast] = useState<string | null>(null);
  const flash = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2200);
  };
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const tellHer = async () => {
    const r = await shareMessage({ text: t("share.her"), url: `${origin}/app`, title: "Baaki" });
    if (r === "copied") flash(t("next.copied"));
  };
  const tellFriend = async () => {
    const r = await shareMessage({ text: t("share.friend"), url: `${origin}/check`, title: t("hero.title") });
    if (r === "copied") flash(t("next.copied"));
  };
  const downloadIcs = () => {
    const url = URL.createObjectURL(icsFile(t("reminder.title"), t("reminder.details")));
    const a = document.createElement("a");
    a.href = url;
    a.download = "payday-reminder.ics";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  };

  return (
    <main className={cx("screen", "fc-page")} lang={htmlLang}>
      <AppBar
        left={
          <Link href="/" className="fc-brand" aria-label="Baaki home">
            <Logo size={30} telugu={false} />
          </Link>
        }
        right={<ThemeToggle />}
      />

      {/* ---------------------------------------------------------- hero */}
      <header className="fc-hero">
        <p className="fc-kicker">{t("hero.kicker")}</p>
        <h1 className={cx("display", "fc-title")}>{t("hero.title")}</h1>
        <p className="fc-sub">{t("hero.sub")}</p>
        <div className={cx("segmented", "fc-langs")} role="group" aria-label={t("lang.label")}>
          {LANG_OPTIONS.map((l) => (
            <button key={l.id} type="button" aria-pressed={lang === l.id} onClick={() => chooseLang(l.id)} lang={l.htmlLang}>
              {l.label}
            </button>
          ))}
        </div>
      </header>

      {/* ---------------------------------------------------------- the questions */}
      <section className={cx("card", "fc-form")} data-tone="glow" aria-label={t("page.title")}>
        {tries > 0 || voice.kind !== "idle" ? (
          <div className="fc-bolo">
            {voice.kind !== "rest" && tries > 0 ? (
              <button
                type="button"
                className={cx("fc-bolo-btn", recording && "fc-bolo-live")}
                onClick={() => rec.toggle()}
                disabled={!micUsable && !recording}
                aria-pressed={recording}
              >
                <span className="fc-bolo-icon" aria-hidden="true">
                  {recording ? <StopIcon /> : <MicIcon />}
                </span>
                <span className="fc-bolo-text">
                  {recording ? t("bolo.listening") : voice.kind === "working" ? t("bolo.working") : t("bolo.button")}
                </span>
                {recording ? <Waveform active level={Math.max(0.25, rec.level)} bars={12} className="fc-bolo-wave" /> : null}
              </button>
            ) : null}
            {voice.kind === "idle" && !recording ? <p className="fc-bolo-hint">{t("bolo.example")}</p> : null}
            {voice.kind === "heard" ? (
              <p className="fc-heard" aria-live="polite">
                <span className="fc-heard-label">{t("bolo.heard")}:</span> “{voice.transcript || "…"}”
                {voice.missing.length ? <> {t("bolo.missing")}</> : null}
              </p>
            ) : null}
            {voice.kind === "rest" || rec.error ? (
              <p className="fc-bolo-hint" role="status">
                {t("bolo.rest")}
              </p>
            ) : null}
            {tries > 0 && voice.kind !== "rest" ? (
              <p className="fc-bolo-meta">
                {t("bolo.left", { n: tries })} · {t("bolo.privacy")}
              </p>
            ) : null}
          </div>
        ) : null}

        <fieldset className="fc-q">
          <legend className="fc-q-label">
            <span className="fc-q-num">1</span>
            {t("q.work")}
          </legend>
          <div className="fc-work-grid">
            {WORK.map((w) => (
              <button
                key={w.id}
                type="button"
                className={cx("choice", "fc-work")}
                aria-pressed={work === w.id}
                onClick={() => setWork(w.id)}
              >
                <span className="fc-work-icon" aria-hidden="true">
                  <w.Icon />
                </span>
                <span className="fc-work-name">{t(`work.${w.id}` as const)}</span>
                <span className="fc-work-sub">{t(`work.${w.id}.sub` as const)}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="fc-q">
          <legend className="fc-q-label">
            <span className="fc-q-num">2</span>
            {t("q.hours")}
            <span className="fc-stepper">
              <button
                type="button"
                className="fc-step"
                aria-label={t("hours.less")}
                onClick={() => setHours((h) => Math.max(0.5, (h ?? 1) - 0.5))}
              >
                −
              </button>
              <span className="fc-q-value" aria-live="polite">
                {hours !== null ? `${hours} ${t("hours.unit")}` : "–"}
              </span>
              <button
                type="button"
                className="fc-step"
                aria-label={t("hours.more")}
                onClick={() => setHours((h) => Math.min(16, (h ?? 0) + 0.5))}
              >
                +
              </button>
            </span>
          </legend>
          <div className="fc-chips">
            {HOUR_CHIPS.map((h) => (
              <button key={h} type="button" className="fc-chip" aria-pressed={hours === h} onClick={() => setHours(h)}>
                {h}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="fc-q">
          <legend className="fc-q-label">
            <span className="fc-q-num">3</span>
            {t("q.days")}
          </legend>
          <div className="fc-days">
            {DAYS.map((d) => (
              <button key={d} type="button" className="fc-chip" aria-pressed={days === d} onClick={() => setDays(d)}>
                {d}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="fc-q">
          <label className="fc-q-label" htmlFor="fc-pay">
            <span className="fc-q-num">4</span>
            {t("q.pay")}
          </label>
          <div className="fc-pay-box">
            <span className="fc-rupee" aria-hidden="true">
              ₹
            </span>
            <input
              id="fc-pay"
              className="fc-pay-input"
              inputMode="numeric"
              autoComplete="off"
              enterKeyHint="done"
              placeholder={t("pay.placeholder")}
              value={grouped(pay)}
              onChange={(e) => setPay(digits(e.target.value))}
            />
            <span className="fc-pay-unit">/ {t("result.month")}</span>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- the result */}
      <section ref={resultRef} className="fc-result-wrap" aria-live="polite" aria-busy={status.kind === "loading"}>
        {!complete ? (
          <p className="fc-placeholder">{t("result.fill")}</p>
        ) : status.kind === "error" ? (
          <div className={cx("card", "fc-error")}>
            <p>{t("err.generic")}</p>
            <button type="button" className="btn btn-small" onClick={() => setAttempt((a) => a + 1)}>
              {t("err.retry")}
            </button>
          </div>
        ) : status.kind === "done" ? (
          <Result r={status.result} t={t} />
        ) : (
          <div className={cx("card", "fc-loading-card")} role="status">
            <span className="fc-shimmer" />
            <span className="fc-shimmer-sm" />
            <span className="visually-hidden">{t("result.loading")}</span>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------- next steps */}
      {status.kind === "done" ? (
        <section className="fc-next" aria-label={t("next.title")}>
          <h2 className="fc-next-title">{t("next.title")}</h2>
          <GradientButton onClick={tellHer} icon={<HeartGlyph />}>
            {t("next.tell")}
          </GradientButton>
          <a
            className="btn btn-big"
            href={googleCalendarUrl(t("reminder.title"), t("reminder.details"))}
            target="_blank"
            rel="noopener noreferrer"
          >
            <CalendarGlyph />
            <span>{t("next.reminder")}</span>
          </a>
          <div className="fc-next-row">
            <button type="button" className="btn btn-ghost btn-small" onClick={downloadIcs}>
              {t("next.ics")}
            </button>
            <button type="button" className="btn btn-ghost btn-small" onClick={tellFriend}>
              <UsersGlyph />
              <span>{t("next.friend")}</span>
            </button>
          </div>
        </section>
      ) : null}

      <p className="fc-foot">
        <CheckIcon className="fc-foot-icon" /> {t("foot.private")}
      </p>
      {toast ? (
        <p className="fc-toast" role="status">
          <ShareIcon /> {toast}
        </p>
      ) : null}
    </main>
  );
}

// ------------------------------------------------------------------ result card
function Result({ r, t }: { r: CheckResult; t: CheckT }) {
  const minimum = useCountTo(r.minimum_monthly);
  const perDay = useCountTo(r.per_day_to_close, 1100);
  const fair = r.verdict === "fair";
  const minLabel = r.is_estimate ? t("result.minimum.est") : t("result.minimum");

  return (
    <article className={cx("card", "fc-result", fair && "fc-result-fair")} data-verdict={r.verdict}>
      {fair ? <Confetti pieces={28} /> : null}

      {fair ? (
        <div className="fc-fair-head">
          <span className="fc-fair-tick" aria-hidden="true">
            <CheckIcon />
          </span>
          <h2 className={cx("display", "fc-fair-title")}>{t("result.fair.title")}</h2>
          <p className="fc-fair-sub">{t("result.fair.sub", { pay: inr(r.monthly_pay), min: inr(r.minimum_monthly) })}</p>
        </div>
      ) : null}

      <div className="fc-min-block">
        <p className="fc-min-label">{minLabel}</p>
        <p className="fc-min-value">
          <span className={cx("grad-text", "fc-min-num")} aria-hidden="true">
            {r.is_estimate ? inr(Math.round(minimum * 2) / 2) : inrWhole(minimum)}
          </span>
          <span className="visually-hidden">{inr(r.minimum_monthly)}</span>
          <span className="fc-min-unit">/ {t("result.month")}</span>
        </p>
        {r.is_estimate ? (
          <div className="fc-estimate">
            <span className="fc-estimate-badge">{t("result.estimate")}</span>
            <span className="fc-estimate-why">{t("result.estimate.why")}</span>
          </div>
        ) : (
          <StatusPill tone="success">
            {t("result.notified")} · {r.category_label}
          </StatusPill>
        )}
      </div>

      {!fair ? (
        <>
          <dl className="fc-rows">
            <div>
              <dt>{t("result.youpay")}</dt>
              <dd>{inr(r.monthly_pay)}</dd>
            </div>
            <div>
              <dt>{t("result.gap")}</dt>
              <dd className="fc-gap">{inr(r.gap_monthly)}</dd>
            </div>
          </dl>
          <div className="fc-per-day">
            <span className="fc-per-day-pre">{t("result.perday.pre")}</span>
            <span className="fc-per-day-num" aria-hidden="true">
              {inrWhole(perDay)}
            </span>
            <span className="visually-hidden">{inrWhole(r.per_day_to_close)}</span>
            <span className="fc-per-day-post">{t("result.perday.post")}</span>
          </div>
          <p className="fc-year">{t("result.year", { amount: inr(r.gap_yearly) })}</p>
        </>
      ) : null}

      <details className="fc-details">
        <summary>{t("result.how")}</summary>
        <p>{r.how}</p>
        <p className="fc-small">{r.order_line}</p>
      </details>
      {r.notes.length ? (
        <details className="fc-details">
          <summary>{t("result.notes")}</summary>
          <ul>
            {r.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      ) : null}
      <details className="fc-details">
        <summary>{t("result.source")}: G.O.Ms.No.6 (30.05.2026)</summary>
        <p className="fc-small">{r.source}</p>
        <a className="fc-link" href={r.source_url} target="_blank" rel="noopener noreferrer">
          {t("result.source.open")}
        </a>
      </details>
      <p className="fc-disclaimer">{t("result.disclaimer")}</p>
    </article>
  );
}
