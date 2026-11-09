"use client";

// Kaam Diary (/diary): a calm day-by-day work / pay log. A month grid (worked = butter, pay received = sage,
// off = rose, proof = lilac), a 5-second check-in (one tap per home, or say it), and the entries as receipts
// grouped by day, with the hash-chain "untouched record" badge.

import { useMemo, useState } from "react";
import { useDashboard, useDiary, usePressToTalk, useSettings, useT } from "@/hooks";
import { shortHash } from "@/lib/format";
import type { UiLang } from "@/lib/i18n";
import type { DiaryEntry } from "@/lib/types";
import { ErrorNote, Loading, MicButton, Screen, Skeleton } from "@/components/ui/primitives";
import { BackIcon, CheckIcon, CrossIcon, FileIcon, HomeIcon, LockIcon, RupeeIcon } from "@/components/ui/icons";

const LOCALE: Record<UiLang, string> = { te: "te-IN", "hi-en": "hi-IN", en: "en-IN" };
const HOME_WASH = ["sky", "peach", "lilac", "sage", "butter", "rose"] as const;

// Screen-only copy (the shared i18n keys cover the rest).
const DX: Record<UiLang, {
  h1: string; em: string; sub: string; worked: string; paid: string; off: string; proof: string;
  daysWorked: string; payments: string; proofs: string; all: string; none: string; prev: string; next: string;
}> = {
  en: {
    h1: "Every day you", em: "worked", sub: "One tap a day. Kept as an untouched record you can show anyone.",
    worked: "Worked", paid: "Pay received", off: "Off", proof: "Proof",
    daysWorked: "days worked", payments: "pay received", proofs: "proofs saved",
    all: "Show all", none: "Nothing logged on this day.", prev: "Previous month", next: "Next month",
  },
  te: {
    h1: "మీరు పని చేసిన", em: "ప్రతి రోజు", sub: "రోజుకు ఒక్క ట్యాప్. ఎవరికైనా చూపించగల మార్చలేని రికార్డు.",
    worked: "పని చేశారు", paid: "జీతం వచ్చింది", off: "సెలవు", proof: "రుజువు",
    daysWorked: "పని రోజులు", payments: "జీతం వచ్చింది", proofs: "రుజువులు",
    all: "అన్నీ చూపించు", none: "ఈ రోజు ఏమీ రాయలేదు.", prev: "ముందు నెల", next: "తర్వాత నెల",
  },
  "hi-en": {
    h1: "Har din ka", em: "hisaab", sub: "Din mein ek tap. Ek pakka record jo aap kisi ko bhi dikha sakte hain.",
    worked: "Kaam kiya", paid: "Paisa mila", off: "Chhutti", proof: "Saboot",
    daysWorked: "kaam ke din", payments: "paisa mila", proofs: "saboot",
    all: "Sab dikhao", none: "Is din kuch nahi likha.", prev: "Pichhla mahina", next: "Agla mahina",
  },
};

type Kind = "checkin" | "payment" | "absence" | "note" | "evidence";
/** Which colour wins when a day has several entries: pay > off > worked > proof. */
const RANK: Record<string, number> = { payment: 4, absence: 3, checkin: 2, evidence: 1, note: 1 };

/** Local IST date key (YYYY-MM-DD) for a timestamp. */
function dayKey(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return new Date(d.getTime() + 5.5 * 3600_000).toISOString().slice(0, 10);
}
function istToday(): string {
  return new Date(Date.now() + 5.5 * 3600_000).toISOString().slice(0, 10);
}
function KindIcon({ kind }: { kind: string }) {
  if (kind === "payment") return <RupeeIcon />;
  if (kind === "absence") return <CrossIcon />;
  if (kind === "note" || kind === "evidence") return <FileIcon />;
  return <HomeIcon />;
}

export function DiaryScreen() {
  const settings = useSettings();
  const { t, lang } = useT();
  const L = DX[lang] ?? DX.en;
  const loc = LOCALE[lang] ?? "en-IN";
  const workerId = settings.hydrated ? settings.workerId : null;
  const dash = useDashboard(workerId);
  const diary = useDiary(workerId, { lang: settings.listenLang });
  const press = usePressToTalk(diary.recorder, { disabled: diary.saving });
  const [picked, setPicked] = useState<string | null>(null);
  const [monthOffset, setMonthOffset] = useState(0);

  const homes = useMemo(
    () => dash.cards.filter((c) => c.employer).map((c) => ({ caseId: c.case_id, employer: c.employer! })),
    [dash.cards],
  );
  const nameOf = (id: number | null) => homes.find((h) => h.employer.id === id)?.employer.name ?? "";

  // day -> strongest kind + entries
  const byDay = useMemo(() => {
    const m = new Map<string, { kind: Kind; items: DiaryEntry[] }>();
    for (const e of diary.entries) {
      const k = dayKey(e.timestamp);
      const cur = m.get(k);
      const kind = e.kind as Kind;
      if (!cur) m.set(k, { kind, items: [e] });
      else {
        cur.items.push(e);
        if ((RANK[kind] ?? 0) > (RANK[cur.kind] ?? 0)) cur.kind = kind;
      }
    }
    return m;
  }, [diary.entries]);

  // The month shown: the latest entry's month (or this month), shifted by the arrows.
  const today = istToday();
  // Open on the fullest recent month (most days logged; the later month wins a tie), so the grid tells a story.
  const anchor = useMemo(() => {
    const perMonth = new Map<string, number>();
    for (const k of byDay.keys()) if (k <= today) perMonth.set(k.slice(0, 7), (perMonth.get(k.slice(0, 7)) ?? 0) + 1);
    let best = today.slice(0, 7);
    let bestN = perMonth.get(best) ?? 0;
    for (const [m, n] of perMonth) if (n > bestN || (n === bestN && m > best)) [best, bestN] = [m, n];
    return `${best}-01`;
  }, [byDay, today]);
  const view = useMemo(() => {
    const [y, mo] = anchor.split("-").map(Number);
    const d = new Date(Date.UTC(y, mo - 1 + monthOffset, 1));
    return { y: d.getUTCFullYear(), m: d.getUTCMonth() };
  }, [anchor, monthOffset]);
  const monthPrefix = `${view.y}-${String(view.m + 1).padStart(2, "0")}`;
  const daysIn = new Date(Date.UTC(view.y, view.m + 1, 0)).getUTCDate();
  const lead = (new Date(Date.UTC(view.y, view.m, 1)).getUTCDay() + 6) % 7; // Monday first
  const monthName = new Date(Date.UTC(view.y, view.m, 1)).toLocaleDateString(loc, { month: "long", year: "numeric", timeZone: "UTC" });
  const dows = Array.from({ length: 7 }, (_, i) =>
    new Date(Date.UTC(2024, 0, 1 + i)).toLocaleDateString(loc, { weekday: "narrow", timeZone: "UTC" }),
  );
  const earliest = diary.entries.length ? dayKey(diary.entries[diary.entries.length - 1].timestamp).slice(0, 7) : monthPrefix;

  const stats = useMemo(() => {
    let worked = 0;
    let paid = 0;
    let proofs = 0;
    for (const [k, v] of byDay) {
      if (!k.startsWith(monthPrefix)) continue;
      if (v.items.some((e) => e.kind === "checkin")) worked += 1;
      paid += v.items.filter((e) => e.kind === "payment").length;
      proofs += v.items.filter((e) => (e.kind as string) === "evidence" || e.kind === "note").length;
    }
    return { worked, paid, proofs };
  }, [byDay, monthPrefix]);

  // Entries grouped by day (newest first), optionally only the picked day.
  const groups = useMemo(() => {
    const out: { key: string; items: DiaryEntry[] }[] = [];
    for (const e of diary.entries) {
      const k = dayKey(e.timestamp);
      if (picked && k !== picked) continue;
      const last = out[out.length - 1];
      if (last && last.key === k) last.items.push(e);
      else out.push({ key: k, items: [e] });
    }
    return out;
  }, [diary.entries, picked]);

  const dayLabel = (k: string) =>
    new Date(`${k}T00:00:00`).toLocaleDateString(loc, { weekday: "long", day: "numeric", month: "long" });
  const timeLabel = (iso: string) => new Date(iso).toLocaleTimeString(loc, { hour: "numeric", minute: "2-digit" });

  return (
    <Screen title={t("diary.title")} back="/app" t={t} className="fx diary-fx" nav="diary">
      <header className="dx-head">
        <h2 className="fx-h" lang={lang === "te" ? "te" : undefined}>
          {L.h1} <em>{L.em}</em>
        </h2>
        <p className="fx-sub">{L.sub}</p>
      </header>

      {/* month grid */}
      <section className="fx-panel dx-cal" aria-label={monthName}>
        <div className="dx-cal-top">
          <p className="dx-month">{monthName}</p>
          <div className="dx-nav">
            <button type="button" aria-label={L.prev} onClick={() => setMonthOffset((o) => o - 1)} disabled={monthPrefix <= earliest}>
              <BackIcon />
            </button>
            <button type="button" aria-label={L.next} onClick={() => setMonthOffset((o) => o + 1)} disabled={monthPrefix >= today.slice(0, 7)}>
              <BackIcon />
            </button>
          </div>
        </div>
        <ol className="dx-grid">
          {dows.map((d, i) => (
            <li key={`dow-${i}`} className="dx-dow" aria-hidden="true">
              {d}
            </li>
          ))}
          {Array.from({ length: lead }).map((_, i) => (
            <li key={`pad-${i}`} aria-hidden="true" />
          ))}
          {Array.from({ length: daysIn }).map((_, i) => {
            const k = `${monthPrefix}-${String(i + 1).padStart(2, "0")}`;
            const d = byDay.get(k);
            return (
              <li key={k}>
                <button
                  type="button"
                  className="dx-day"
                  data-kind={d?.kind}
                  data-today={k === today}
                  aria-pressed={picked === k}
                  aria-label={`${dayLabel(k)}${d ? ` · ${d.items.length}` : ""}`}
                  disabled={!d}
                  style={{ animationDelay: `${Math.min(i * 12, 360)}ms` }}
                  onClick={() => setPicked((p) => (p === k ? null : k))}
                >
                  {i + 1}
                </button>
              </li>
            );
          })}
        </ol>
        <div className="dx-legend">
          <span className="fx-chip" data-wash="butter"><span className="fx-chip-dot" />{L.worked}</span>
          <span className="fx-chip" data-wash="sage"><span className="fx-chip-dot" />{L.paid}</span>
          <span className="fx-chip" data-wash="rose"><span className="fx-chip-dot" />{L.off}</span>
          <span className="fx-chip" data-wash="lilac"><span className="fx-chip-dot" />{L.proof}</span>
        </div>
        <div className="dx-stats">
          <p className="dx-stat" data-wash="butter"><b>{stats.worked}</b><span>{L.daysWorked}</span></p>
          <p className="dx-stat" data-wash="sage"><b>{stats.paid}</b><span>{L.payments}</span></p>
          <p className="dx-stat" data-wash="lilac"><b>{stats.proofs}</b><span>{L.proofs}</span></p>
        </div>
      </section>

      {/* 5-second check-in */}
      <section className="fx-panel dx-checkin" aria-label={t("diary.checkin")}>
        <div>
          <h2 className="fx-h2">{t("diary.checkin")}</h2>
          <p className="fx-muted" style={{ marginTop: 4 }}>{t("diary.hint")}</p>
        </div>
        <div className="dx-homes">
          {homes.map((h, i) => (
            <button
              key={h.caseId}
              type="button"
              className="dx-home"
              disabled={diary.saving}
              onClick={() =>
                void diary.add({
                  text: `${t("diary.worked_at")}: ${h.employer.name}`,
                  employerId: h.employer.id,
                  caseId: h.caseId,
                  kind: "checkin",
                })
              }
            >
              <span className="fx-avatar" data-wash={HOME_WASH[i % HOME_WASH.length]} aria-hidden="true">
                {(h.employer.name || "?").trim().charAt(0).toUpperCase()}
              </span>
              <span>{h.employer.name}</span>
            </button>
          ))}
        </div>
        <div className="dx-say">
          <MicButton
            size="small"
            state={diary.saving ? "busy" : diary.recorder.state}
            level={diary.recorder.level}
            elapsedMs={diary.recorder.elapsedMs}
            disabled={diary.saving}
            handlers={press}
            label={diary.recorder.state === "recording" ? t("speak.stop") : t("diary.voice")}
          />
          {diary.last ? (
            <p className="dx-saved" role="status">
              <CheckIcon /> {t("diary.saved")}
            </p>
          ) : null}
        </div>
        <ErrorNote message={diary.error} />
      </section>

      {diary.loading ? <Loading label={t("common.loading")} /> : null}
      <section aria-label={t("diary.entries")}>
        <div className="dx-entries-head">
          <h2 className="section-title">{picked ? dayLabel(picked) : t("diary.entries")}</h2>
          {picked ? (
            <button type="button" className="dx-clear" onClick={() => setPicked(null)}>
              {L.all}
            </button>
          ) : diary.chain ? (
            <p className="dx-chain" data-valid={diary.chain.valid}>
              <LockIcon />
              {diary.chain.valid ? t("diary.valid") : t("diary.broken")} · {diary.chain.count}
            </p>
          ) : null}
        </div>
        {diary.loading && !diary.entries.length ? (
          <div className="stack" aria-hidden="true">
            <Skeleton height={64} radius={20} />
            <Skeleton height={64} radius={20} />
          </div>
        ) : null}
        {picked && !groups.length ? <p className="dx-empty">{L.none}</p> : null}
        <div className="diary-list-fx">
          {groups.map((g) => (
            <div key={g.key} className="dx-day-group">
              {!picked ? <p className="dx-day-label">{dayLabel(g.key)}</p> : null}
              <ol className="dx-list">
                {g.items.map((e, i) => (
                  <li key={e.id} className="dx-entry" data-kind={e.kind} style={{ animationDelay: `${i * 40}ms` }}>
                    <span className="dx-kind" aria-hidden="true">
                      <KindIcon kind={e.kind} />
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <p className="dx-entry-text">{e.text}</p>
                      <p className="dx-entry-meta">
                        <span>
                          {timeLabel(e.timestamp)}
                          {e.employer_id ? ` · ${nameOf(e.employer_id)}` : ""}
                        </span>
                        <span className="fx-mono" title={e.hash}>
                          #{shortHash(e.hash)}
                        </span>
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </section>
    </Screen>
  );
}
