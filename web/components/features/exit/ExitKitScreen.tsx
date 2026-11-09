"use client";

// Exit Kit (/exit?employer=&case=): "Madam said don't come from tomorrow."
// 1. The DATE final dues should be paid by (s.17(2), two working days; no hours-and-minutes clock).
// 2. What is owed: this month's days (pro-rata), earlier unpaid months from the case, the minimum-wage
//    gap as a labelled estimate (never in the total).
// 3. Four things to collect before leaving the gate, read aloud from the Timbre cache.
// 4. One tap: the normal Polite step through the existing case / message endpoints.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useDashboard, useListen, usePressToTalk, useSettings, useT } from "@/hooks";
import { CheckIcon, ArrowRightIcon } from "@/components/ui/icons";
import { AssetSlot } from "@/components/ui/AssetSlot";
import type { UiLang } from "@/lib/i18n";
import { errorMessage, isAbort } from "@/lib/api";
import { inr, itemLabel, monthLabel, shortDate } from "@/lib/format";
import { computeExit, exitLangOf, speakChecklist, startPolite, type ChecklistItem, type ExitItem, type ExitResult } from "@/lib/features/exit";
import {
  Card,
  CountUp,
  ErrorNote,
  EstimateTag,
  GradientButton,
  Loading,
  MicButton,
  Money,
  PlayButton,
  Screen,
  Skeleton,
  Sources,
  StatusPill,
  avatarTone,
} from "@/components/ui/primitives";

// Screen-only headline (everything else comes from ./strings).
const XK: Record<UiLang, { h1: string; em: string; which: string }> = {
  en: { h1: "Asked to leave?", em: "Take what is yours.", which: "Which home?" },
  te: { h1: "పని మానేయమన్నారా?", em: "మీది తీసుకుని వెళ్ళండి.", which: "ఏ ఇల్లు?" },
  "hi-en": { h1: "Kaam chhodne ko kaha?", em: "Apna haq lekar jaiye.", which: "Kaunsa ghar?" },
};
import { exitStrings, type ExitT } from "./strings";

const css = {
  listRow: { display: "flex", flexDirection: "column", gap: "var(--s-2)", flex: 1, minWidth: 0 } as CSSProperties,
  grid2: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--s-3)" } as CSSProperties,
};

function weekdayDate(iso: string, lang: string): string {
  const d = new Date(`${iso}T00:00:00`);
  const loc = lang === "te" ? "te-IN" : lang === "hi-en" ? "hi-IN" : "en-IN";
  return d.toLocaleDateString(loc, { weekday: "short", day: "numeric", month: "short" });
}

// ------------------------------------------------------------------ checklist player (queue)
function useClipQueue() {
  const audio = useRef<HTMLAudioElement | null>(null);
  const queue = useRef<string[]>([]);
  const advance = useRef<() => void>(() => {});
  const [current, setCurrent] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const next = useCallback(() => {
    const url = queue.current.shift() ?? null;
    setCurrent(url);
    setProgress(0);
    if (!url) return;
    if (!audio.current) {
      const a = new Audio();
      a.addEventListener("ended", () => advance.current());
      a.addEventListener("error", () => advance.current());
      a.addEventListener("timeupdate", () => {
        if (a.duration && Number.isFinite(a.duration)) setProgress(a.currentTime / a.duration);
      });
      audio.current = a;
    }
    audio.current.src = url;
    void audio.current.play().catch(() => setCurrent(null));
  }, []);

  useEffect(() => {
    advance.current = next;
  }, [next]);

  const play = useCallback(
    (urls: string[]) => {
      audio.current?.pause();
      queue.current = [...urls];
      next();
    },
    [next],
  );
  const stop = useCallback(() => {
    queue.current = [];
    audio.current?.pause();
    setCurrent(null);
  }, []);
  useEffect(() => () => audio.current?.pause(), []);
  return { current, progress, play, stop };
}

// ------------------------------------------------------------------ pieces
function ItemRow({ it, x, t, lang }: { it: ExitItem; x: ExitT; t: ReturnType<typeof useT>["t"]; lang: string }) {
  let label: string;
  if (it.kind === "final_settlement") label = x("part_label", { days: it.days_worked ?? 0, month: monthLabel(it.month, lang) });
  else if (it.kind === "paid_back") label = x("paid_back");
  else if (it.kind === "advance_recovery") label = x("advance");
  else label = itemLabel(t, it, lang);
  return (
    <li className="ex-line" data-kind={it.kind} data-included={it.included_in_total}>
      <div className="ex-line-row">
        <span className="ex-line-label" title={it.label}>
          {label} {it.is_estimate ? <EstimateTag t={t} /> : null}
        </span>
        <Money value={it.amount} className="ex-line-amt" />
      </div>
      {it.kind === "final_settlement" && it.basis ? <p className="fx-muted" style={{ marginTop: 4 }}>{it.basis}</p> : null}
      {it.kind === "min_wage_shortfall" && !it.included_in_total ? <p className="fx-muted" style={{ marginTop: 4 }}>{x("shortfall_note")}</p> : null}
      {it.from_case && it.kind !== "min_wage_shortfall" ? <p className="fx-muted" style={{ marginTop: 4 }}>{x("from_case")}</p> : null}
    </li>
  );
}

// ------------------------------------------------------------------ screen
export function ExitKitScreen({ employerId, caseId }: { employerId: number | null; caseId: number | null }) {
  const settings = useSettings();
  const { t, lang } = useT();
  const x = useMemo(() => exitStrings(lang), [lang]);
  const router = useRouter();
  const workerId = settings.hydrated ? settings.workerId : null;
  const clLang = exitLangOf(lang);
  const H = XK[lang] ?? XK.en;
  const dash = useDashboard(employerId == null && caseId == null ? workerId : null);

  const [res, setRes] = useState<ExitResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastDay, setLastDay] = useState<string>("");
  const [days, setDays] = useState<string>("");
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioFailed, setAudioFailed] = useState(false);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [amountSaid, setAmountSaid] = useState("");
  const [contact, setContact] = useState("");
  const [sending, setSending] = useState(false);
  const [heard, setHeard] = useState<string | null>(null);
  const clips = useClipQueue();

  const run = useCallback(
    async (opts: { lastDay?: string; days?: string; transcript?: string } = {}) => {
      if (workerId == null || (employerId == null && caseId == null)) return;
      setLoading(true);
      setError(null);
      try {
        const r = await computeExit({
          worker_id: workerId,
          employer_id: employerId,
          case_id: caseId,
          last_day: opts.transcript ? null : opts.lastDay || null,
          days_worked_this_month: opts.days ? Number(opts.days) : null,
          transcript: opts.transcript,
          lang: clLang,
        });
        setRes(r);
        setLastDay(r.last_day);
        setDays(String(r.basis.days_worked));
        setChecklist(r.checklist);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [workerId, employerId, caseId, clLang],
  );

  // something happens in the first second: the date and the amount appear straight away
  useEffect(() => {
    if (workerId == null || (employerId == null && caseId == null)) return;
    const ac = new AbortController();
    computeExit({ worker_id: workerId, employer_id: employerId, case_id: caseId, lang: clLang }, ac.signal).then(
      (r) => {
        setRes(r);
        setLastDay(r.last_day);
        setDays(String(r.basis.days_worked));
        setChecklist(r.checklist);
      },
      (err) => {
        if (!isAbort(err)) setError(errorMessage(err));
      },
    );
    return () => ac.abort();
  }, [workerId, employerId, caseId, clLang]);

  const listen = useListen({
    lang: settings.listenLang,
    useLlm: false,
    maxMs: 30_000,
    onResult: (r, { final }) => {
      if (!final) return;
      setHeard(r.transcript);
      void run({ transcript: r.transcript, days });
    },
  });
  const press = usePressToTalk(listen.recorder, { disabled: listen.status === "listening" || loading });

  const ensureAudio = useCallback(async (): Promise<ChecklistItem[]> => {
    if (checklist.length && checklist.every((c) => c.audio_url)) return checklist;
    setAudioBusy(true);
    try {
      const r = await speakChecklist(clLang);
      setChecklist(r.checklist);
      setAudioFailed(r.fallback === "text");
      return r.checklist;
    } catch {
      setAudioFailed(true);
      return checklist;
    } finally {
      setAudioBusy(false);
    }
  }, [checklist, clLang]);

  const playOne = async (id: string) => {
    if (clips.current && checklist.find((c) => c.id === id)?.audio_url === clips.current) return clips.stop();
    const list = await ensureAudio();
    const url = list.find((c) => c.id === id)?.audio_url;
    if (url) clips.play([url]);
  };
  const playAll = async () => {
    const list = await ensureAudio();
    const urls = list.map((c) => c.audio_url).filter((u): u is string => !!u);
    if (urls.length) clips.play(urls);
  };

  const onPolite = async () => {
    if (!res) return;
    setSending(true);
    setError(null);
    const said = amountSaid ? ` They said ${inr(Number(amountSaid))}.` : "";
    const who = contact ? ` Contact: ${contact}.` : "";
    const note = `Asked to leave. Last working day ${res.last_day}. Exit Kit count ${inr(res.total)}, should be paid by ${res.due_by}.${said}${who}`;
    try {
      const out = await startPolite(res, note);
      router.push(`/case/${out.caseId}`);
    } catch (err) {
      setError(errorMessage(err));
      setSending(false);
    }
  };

  // ---------------------------------------------------------------- render
  if (settings.hydrated && workerId == null) {
    return (
      <Screen title={x("title")} back="/app" t={t} className="fx">
        <ErrorNote message={x("no_worker")} />
      </Screen>
    );
  }
  if (employerId == null && caseId == null) {
    // No home in the link: let her pick one right here instead of sending her back.
    // One row per home (employer), even when a home has more than one case.
    const homes = dash.cards.filter((c, i, all) => c.employer && all.findIndex((o) => o.employer?.id === c.employer!.id) === i);
    return (
      <Screen title={x("title")} back="/app" t={t} className="fx">
        <header className="dx-head">
          <h2 className="fx-h" lang={lang === "te" ? "te" : undefined}>
            {H.h1} <em>{H.em}</em>
          </h2>
          <p className="fx-sub">{x("intro")}</p>
        </header>
        {settings.hydrated ? (
          <AssetSlot name="exit-kit-gate" alt="" ratio="16/10" tone="butter" rounded="var(--card-r)" fit="contain" anchor="bottom" className="slot-bleed" />
        ) : null}
        <section className="fx-panel" aria-label={H.which}>
          <p className="fx-eyebrow">{H.which}</p>
          {dash.loading && !homes.length ? <Skeleton height={60} radius={18} /> : null}
          <ul className="xk-homes">
            {homes.map((c) => (
              <li key={c.case_id}>
                <Link href={`/exit?employer=${c.employer!.id}&case=${c.case_id}`} className="xk-home">
                  <span className="fx-avatar" data-wash={avatarTone(c.employer!.name)} aria-hidden="true">
                    {c.employer!.name.trim().charAt(0).toUpperCase()}
                  </span>
                  <span className="xk-home-name">{c.employer!.name}</span>
                  <ArrowRightIcon />
                </Link>
              </li>
            ))}
          </ul>
          {!dash.loading && !homes.length ? <ErrorNote message={x("no_home")} /> : null}
        </section>
      </Screen>
    );
  }

  const included = res?.items.filter((i) => i.kind !== "min_wage_shortfall") ?? [];
  const estimates = res?.items.filter((i) => i.kind === "min_wage_shortfall") ?? [];
  const canPolite = res && res.polite.mode !== "nothing_due" && res.total > 0;
  const saidNum = Number(amountSaid);

  return (
    <Screen title={res?.employer?.name ? `${x("title")} · ${res.employer.name}` : x("title")} back="/app" t={t} className="exit-screen fx">
      <header className="dx-head">
        <h2 className="fx-h" lang={lang === "te" ? "te" : undefined}>
          {H.h1} <em>{H.em}</em>
        </h2>
        <p className="fx-sub">{x("intro")}</p>
      </header>

      {res?.safety && (res.safety as { flagged?: boolean }).flagged ? (
        <Card tone="warn" href="/safety">
          <strong>{x("safety")}</strong>
        </Card>
      ) : null}

      {/* 1. the date (never a ticking clock) */}
      <section className="fx-panel xk-due" data-wash="butter" aria-live="polite">
        <p className="fx-eyebrow fx-wash-ink">{x("due_label")}</p>
        {res ? <p className="xk-date">{weekdayDate(res.due_by, lang)}</p> : <Skeleton width="70%" height={44} />}
        <p className="fx-muted fx-wash-ink">{x("due_rule")}</p>
        <p className="fx-muted">{x("due_caveat")}</p>
        {res?.last_day_how === "from_tomorrow" ? <p className="fx-muted">{x("last_day_from_tomorrow")}</p> : null}
        <div style={css.grid2}>
          <label className="field">
            <span className="field-label">{x("last_day")}</span>
            <input
              className="input"
              type="date"
              value={lastDay}
              onChange={(e) => setLastDay(e.target.value)}
              onBlur={() => lastDay && lastDay !== res?.last_day && void run({ lastDay, days })}
            />
          </label>
          <label className="field">
            <span className="field-label">{x("days_worked")}</span>
            <input
              className="input"
              type="number"
              inputMode="numeric"
              min={0}
              max={31}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              onBlur={() => days && Number(days) !== res?.basis.days_worked && void run({ lastDay, days })}
            />
          </label>
        </div>
        {res ? (
          <p className="fx-muted">
            {res.basis.days_how === "diary check-ins"
              ? x("days_how_diary")
              : res.basis.days_how === "calendar count"
                ? x("days_how_calendar")
                : x("days_how_said")}
          </p>
        ) : null}
        <p className="fx-muted">{x("our_reading")}</p>
      </section>

      <section className="stack" aria-label={x("say_it")}>
        <MicButton
          size="small"
          state={listen.status === "listening" ? "busy" : listen.recorder.state}
          level={listen.recorder.level}
          elapsedMs={listen.recorder.elapsedMs}
          disabled={listen.status === "listening" || loading}
          handlers={press}
          label={listen.recorder.state === "recording" ? t("speak.stop") : x("say_it")}
        />
        {heard ? (
          <p className="meta">
            {x("heard")}: “{heard}”
          </p>
        ) : null}
        <ErrorNote message={listen.error} />
      </section>

      {/* 2. what is owed */}
      <section className="fx-panel">
        <p className="fx-eyebrow">{x("owed_title")}</p>
        {(loading || !error) && !res ? <Loading label={t("common.loading")} /> : null}
        {res ? (
          <>
            <p className="fx-money">
              <CountUp value={res.total} />
            </p>
            {res.is_estimate_flags.days_worked ? <StatusPill tone="estimate">{t("common.estimate")}</StatusPill> : null}
            <ul className="xk-ledger">
              {included.map((it, i) => (
                <ItemRow key={`${it.kind}-${it.month}-${i}`} it={it} x={x} t={t} lang={lang} />
              ))}
              {estimates.map((it, i) => (
                <ItemRow key={`sf-${it.month}-${i}`} it={it} x={x} t={t} lang={lang} />
              ))}
            </ul>
            {res.notes.length ? <p className="fx-muted">{x("already_counted")}</p> : null}
            <p className="fx-muted">{x("not_claimed")}</p>
          </>
        ) : null}
      </section>

      {/* 3. the gate checklist, read aloud */}
      <section className="fx-panel">
        <div className="fx-row-between">
          <div>
            <h2 className="fx-h2">{x("checklist_title")}</h2>
            <p className="fx-muted" style={{ marginTop: 4 }}>{x("checklist_hint")}</p>
          </div>
          <span className="xk-count" aria-hidden="true">
            {Object.values(done).filter(Boolean).length}/{checklist.length}
          </span>
        </div>
        <ol className="xk-check">
          {checklist.map((c, i) => (
            <li key={c.id} className="xk-item" data-done={!!done[c.id]}>
              <label className="xk-tick">
                <input
                  type="checkbox"
                  checked={!!done[c.id]}
                  onChange={(e) => setDone((d) => ({ ...d, [c.id]: e.target.checked }))}
                  aria-label={`${x("done")} ${i + 1}`}
                />
                <span aria-hidden="true">{done[c.id] ? <CheckIcon /> : i + 1}</span>
              </label>
              <div style={css.listRow}>
                <p className="xk-text">{c.text}</p>
                {c.id === "amount" ? (
                  <>
                    <input
                      className="input"
                      type="number"
                      inputMode="numeric"
                      placeholder={x("amount_said")}
                      aria-label={x("amount_said")}
                      value={amountSaid}
                      onChange={(e) => setAmountSaid(e.target.value)}
                    />
                    {amountSaid && res && Number.isFinite(saidNum) ? (
                      <p className="fx-muted">{x("amount_compare", { amount: inr(res.total) })}</p>
                    ) : null}
                  </>
                ) : null}
                {c.id === "last_day" && res ? <p className="fx-muted">{shortDate(res.last_day, lang)}</p> : null}
                {c.id === "ledger_photo" ? <p className="fx-muted">{x("photo_hint")}</p> : null}
                {c.id === "contact" ? (
                  <input
                    className="input"
                    type="text"
                    placeholder={x("contact")}
                    aria-label={x("contact")}
                    value={contact}
                    onChange={(e) => setContact(e.target.value)}
                  />
                ) : null}
                <PlayButton
                  state={clips.current && clips.current === c.audio_url ? "playing" : audioBusy ? "loading" : "idle"}
                  active={!!c.audio_url && clips.current === c.audio_url}
                  progress={clips.progress}
                  onClick={() => void playOne(c.id)}
                  label={audioBusy ? x("audio_loading") : x("listen")}
                  disabled={audioBusy}
                />
              </div>
            </li>
          ))}
        </ol>
        {checklist.length ? (
          <button type="button" className="fx-pill-btn" onClick={() => void playAll()} disabled={audioBusy}>
            {x("listen_all")}
          </button>
        ) : null}
        {audioFailed ? <p className="fx-muted">{x("audio_fallback")}</p> : null}
      </section>

      <ErrorNote message={error} onRetry={() => void run({ lastDay, days })} retryLabel={t("common.retry")} />

      {/* 4. one tap: the normal Polite step */}
      {res && !canPolite ? <p className="hint">{x("nothing_due")}</p> : null}
      {canPolite ? (
        <section className="stack">
          <GradientButton onClick={() => void onPolite()} disabled={sending || loading}>
            {sending ? x("working") : x("polite_btn", { amount: inr(res.total) })}
          </GradientButton>
          <p className="meta">{x("polite_hint")}</p>
        </section>
      ) : null}

      {res ? <Sources items={res.sources} title={x("sources")} /> : null}
      <p className="footnote">{t("common.not_legal_advice")}</p>
      {res?.case_id ? (
        <p className="meta">
          <Link href={`/case/${res.case_id}`}>{res.employer?.name ?? ""} →</Link>
        </p>
      ) : null}
    </Screen>
  );
}
