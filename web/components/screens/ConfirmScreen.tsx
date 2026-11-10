"use client";

// Confirm (/case/new): which home → a receipt-style read-back (each fact with ✓ / Fix), the money
// worked out step by step with the law source → ✓ Haan / ✗ Nahi.
// Also used by the Case screen to finish a case that is still a draft (resumeCaseId).

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAudioPlayer, useDashboard, useHydrated, useNewCase, useSafety, useSettings, useT, type HomeChoice } from "@/hooks";
import { inr, itemLabel } from "@/lib/format";
import type { UiLang } from "@/lib/i18n";
import type { Employer, LangCode } from "@/lib/types";
import {
  Card,
  ErrorNote,
  EstimateTag,
  GradientButton,
  Loading,
  Money,
  MoneyFigure,
  PlayButton,
  Screen,
  Skeleton,
  Sources,
  StatusPill,
  Toggle,
  avatarTone,
} from "@/components/ui/primitives";
import { CheckIcon, HomeIcon, PenIcon } from "@/components/ui/icons";

// Confirm-only labels (kept local so the shared i18n table stays untouched).
const CONF: Record<
  UiLang,
  {
    how: string;
    checked: (n: number, m: number) => string;
    law: string;
    heard: string;
    check: string;
    retold: (employer: string, was: string | null) => string;
    noWorker: string;
    howManyMonths: string;
    howManyHint: string;
  }
> = {
  en: {
    how: "How it adds up",
    checked: (n, m) => `${n} of ${m} checked`,
    law: "Law",
    heard: "What Baaki heard",
    check: "Check each line",
    retold: (e, was) => `Updating your ${e} case${was ? ` (was ${was})` : ""}. Check the new numbers.`,
    noWorker: "No profile on this server yet. Open Baaki from the start to begin.",
    howManyMonths: "How many months?",
    howManyHint: "Tap Fix and say the number of months.",
  },
  "hi-en": {
    how: "Hisaab kaise bana",
    checked: (n, m) => `${n}/${m} sahi`,
    law: "Kanoon",
    heard: "Baaki ne kya suna",
    check: "Har line check karein",
    retold: (e, was) => `${e} वाला case update हो रहा है${was ? ` (पहले ${was})` : ""}। नए नंबर देख लीजिए।`,
    noWorker: "इस server पर अभी कोई profile नहीं है। Baaki शुरू से खोलिए।",
    howManyMonths: "कितने महीने?",
    howManyHint: "ठीक करें दबाइए और महीनों की गिनती बताइए।",
  },
  te: {
    how: "లెక్క ఎలా వచ్చింది",
    checked: (n, m) => `${n}/${m} సరి`,
    law: "చట్టం",
    heard: "బాకీ విన్నది",
    check: "ప్రతి వివరం చూడండి",
    retold: (e, was) => `${e} కేసు మారుస్తున్నాం${was ? ` (ముందు ${was})` : ""}. కొత్త లెక్క చూడండి.`,
    noWorker: "ఈ సర్వర్‌లో ఇంకా ప్రొఫైల్ లేదు. బాకీని మొదటి నుంచి తెరవండి.",
    howManyMonths: "ఎన్ని నెలలు?",
    howManyHint: "సరిచేయి నొక్కి, ఎన్ని నెలలో చెప్పండి.",
  },
};

const EMPLOYER_LANGS: { value: LangCode; label: string }[] = [
  { value: "hi-en", label: "Hinglish" },
  { value: "te-IN", label: "తెలుగు" },
  { value: "en-IN", label: "English" },
];

type FlowProps = { resumeCaseId?: number | null; onConfirmed?: (id: number) => void };

/** Speak → Check → Send progress header (Agoda-style booking steps). */
export function FlowSteps({ current }: { current: 0 | 1 | 2 }) {
  const { t } = useT();
  const steps = [t("flow.speak"), t("flow.check"), t("flow.send")];
  return (
    <ol className="flow-steps" aria-label={steps.join(" → ")}>
      {steps.map((label, i) => (
        <li key={label} className="flow-step" data-done={i < current} aria-current={i === current ? "step" : undefined}>
          <span className="flow-step-dot" aria-hidden="true">
            {i < current ? <CheckIcon /> : i + 1}
          </span>
          <span className="flow-step-label">{label}</span>
        </li>
      ))}
    </ol>
  );
}

export function ConfirmFlow(props: FlowProps) {
  return (
    <div className="confirm-flow">
      <FlowSteps current={1} />
      <ConfirmFlowBody {...props} />
    </div>
  );
}

function ConfirmFlowBody({ resumeCaseId = null, onConfirmed }: FlowProps) {
  const router = useRouter();
  const settings = useSettings();
  const { t, lang } = useT();
  const dash = useDashboard(settings.hydrated ? settings.workerId : null);
  const player = useAudioPlayer();
  const { raise: raiseSafety } = useSafety();

  const employers = useMemo(() => {
    const seen = new Map<number, Employer>();
    for (const c of dash.cards) if (c.employer) seen.set(c.employer.id, c.employer);
    return [...seen.values()];
  }, [dash.cards]);

  const flow = useNewCase({
    worker: dash.worker,
    employers,
    resumeCaseId,
    onReadback: (r) => {
      if (r.audio_url) void player.play(r.audio_url);
    },
  });

  // A case whose words trip the safety switch goes to the Safety screen instead.
  const flagged = flow.caseData?.safety?.flagged ? flow.caseData.safety : null;
  useEffect(() => {
    if (flagged && flagged.helplines) {
      raiseSafety(flagged as Parameters<typeof raiseSafety>[0]);
      router.push("/safety");
    }
  }, [flagged, raiseSafety, router]);

  useEffect(() => {
    if (flow.phase === "rejected") router.push("/speak");
  }, [flow.phase, router]);

  const [newName, setNewName] = useState<string | null>(null);
  const [newLang, setNewLang] = useState<LangCode | null>(null);
  // ✓ per read-back line: a checklist for her while she listens (Send stays her own tap).
  const [okLines, setOkLines] = useState<Record<string, boolean>>({});
  const C = CONF[lang];

  if (flow.phase === "extracting" || flow.phase === "creating" || (!flow.caseData && flow.phase === "saving")) {
    return (
      <div className="stack confirm-loading">
        <Loading label={t("confirm.reading")} />
        <div className="card receipt receipt-skeleton" aria-hidden="true">
          <Skeleton width="40%" height={12} />
          <Skeleton width="62%" height={40} />
          <Skeleton lines={4} height={14} />
        </div>
      </div>
    );
  }

  if (flow.phase === "error") {
    return (
      <div className="stack">
        <ErrorNote message={flow.noWorker ? CONF[lang].noWorker : flow.error === "nothing_said" ? t("speak.tap") : flow.error} />
        <Link href="/speak" className="btn btn-primary btn-big">
          {t("speak.again")}
        </Link>
      </div>
    );
  }

  // ------------------------------------------------------------------ which home?
  if (flow.phase === "home") {
    const choice = flow.homeChoice;
    const pickedId = choice?.kind === "existing" ? choice.employerId : null;
    const name = newName ?? (choice?.kind === "new" ? choice.name : (flow.facts?.employer_name as string) ?? "");
    const elang = newLang ?? (choice?.kind === "new" ? choice.language : "hi-en");
    const newChoice: HomeChoice = { kind: "new", name, language: elang };
    return (
      <section className="stack" aria-label={t("confirm.which_home")}>
        <h2 className="section-title">{t("confirm.which_home")}</h2>
        <ul className="choice-list">
          {employers.map((e) => (
            <li key={e.id}>
              <button
                type="button"
                className="choice"
                aria-pressed={pickedId === e.id}
                onClick={() => flow.setHome({ kind: "existing", employerId: e.id, name: e.name })}
              >
                <span className="choice-icon" data-tone={avatarTone(e.name)} aria-hidden="true">
                  <HomeIcon />
                </span>
                <span className="choice-text">
                  {e.name}
                  {e.locality ? <span className="muted"> · {e.locality}</span> : null}
                </span>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              className="choice"
              aria-pressed={choice?.kind === "new"}
              onClick={() => flow.setHome(newChoice)}
            >
              <span className="choice-icon choice-icon-new" aria-hidden="true">
                +
              </span>
              <span className="choice-text">{t("confirm.new_home")}</span>
            </button>
          </li>
        </ul>
        {choice?.kind === "new" ? (
          <div className="card stack">
            <label className="field">
              <span className="field-label">{t("confirm.employer_name")}</span>
              <input
                className="input"
                value={name}
                onChange={(e) => {
                  setNewName(e.target.value);
                  flow.setHome({ ...newChoice, name: e.target.value });
                }}
              />
            </label>
            <label className="field">
              <span className="field-label">{t("confirm.employer_lang")}</span>
              <select
                className="input"
                value={elang}
                onChange={(e) => {
                  setNewLang(e.target.value as LangCode);
                  flow.setHome({ ...newChoice, language: e.target.value as LangCode });
                }}
              >
                {EMPLOYER_LANGS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : null}
        <ErrorNote message={flow.error === "employer_name_required" ? t("confirm.employer_name") : flow.error} />
        <GradientButton onClick={() => void flow.chooseHome()} disabled={!choice}>
          {t("confirm.use_this")}
        </GradientButton>
      </section>
    );
  }

  // ------------------------------------------------------------------ review (read-back gate)
  const f = flow.facts;
  const calc = flow.calc;
  const items = calc?.items ?? [];
  const audioUrl = flow.readbackAudioUrl;
  const haq = flow.haq;
  const employerName = flow.caseData?.employer?.name ?? (f?.employer_name as string) ?? "—";
  // The read-back asks back what was unclear ("do teen mahine" -> readback.asks = ["months"]).
  const asks = ((flow.caseData?.readback ?? flow.preview?.readback) as { asks?: unknown } | undefined)?.asks;
  const asksMonths = Array.isArray(asks) && asks.includes("months");

  const onYes = async () => {
    const id = await flow.yes();
    if (id === null) return;
    if (onConfirmed) onConfirmed(id);
    else router.replace(`/case/${id}`);
  };

  const factRows: { k: string; label: string; value: ReactNode; ask?: string }[] = f
    ? [
        { k: "employer", label: t("confirm.employer"), value: employerName },
        { k: "wage", label: t("confirm.wage"), value: <Money value={Number(f.monthly_wage ?? 0)} /> },
        {
          k: "months",
          label: t("confirm.months"),
          // an unclear count is stored as 0 / null: show a dash next to the question, never "0 months"
          value: asksMonths ? "—" : (flow.caseData?.months_unpaid ?? f.months_unpaid ?? "—"),
          ask: asksMonths ? C.howManyMonths : undefined,
        },
        ...(f.hours_per_day ? [{ k: "hours", label: t("confirm.hours"), value: f.hours_per_day as ReactNode }] : []),
        ...(f.deductions?.length ? [{ k: "cuts", label: t("confirm.cuts"), value: f.deductions.map((d) => inr(d.amount)).join(", ") as ReactNode }] : []),
      ]
    : [];
  const okCount = factRows.filter((r) => okLines[r.k]).length;

  return (
    <div className="stack confirm-review">
      {flow.retold ? (
        <p className="retold-note" role="status">
          {C.retold(employerName, flow.retold.previousTotal != null ? inr(flow.retold.previousTotal) : null)}
        </p>
      ) : null}
      <Card as="section" tone="glow" className="readback" aria-live="polite">
        <div className="readback-play">
          {audioUrl ? (
            <PlayButton
              state={player.state}
              active={player.isCurrent(audioUrl)}
              progress={player.progress}
              onClick={() => void player.toggle(audioUrl)}
              label={player.state === "blocked" ? t("common.tap_to_play") : t("confirm.play")}
            />
          ) : flow.readbackLoading ? (
            <Loading label={t("common.loading")} />
          ) : (
            <p className="hint">{t("common.audio_failed")}</p>
          )}
        </div>
        <h2 className="card-title readback-title">{C.heard}</h2>
        <ol className="readback-lines">
          {flow.readbackSentences.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      </Card>

      <section className="card receipt" aria-label={t("confirm.total")}>
        <div className="receipt-head">
          <span className="receipt-avatar" data-tone={avatarTone(employerName)} aria-hidden="true">
            {employerName.slice(0, 1).toUpperCase()}
          </span>
          <div className="receipt-head-text">
            <p className="total-label">{t("confirm.total")}</p>
            <p className="total-value">
              <MoneyFigure value={flow.total} size="lg" />
            </p>
            {flow.draft.summary && flow.draft.summary.total !== flow.total ? (
              <p className="meta">
                {t("confirm.you_said")}: {inr(flow.draft.summary.total)}
              </p>
            ) : null}
          </div>
        </div>

        {factRows.length ? (
          <div className="receipt-section receipt-check">
            <div className="receipt-section-head">
              <p className="eyebrow">{C.check}</p>
              <span className="receipt-count" data-all={okCount === factRows.length}>
                {C.checked(okCount, factRows.length)}
              </span>
            </div>
            <dl className="facts receipt-facts">
              {factRows.map((r) => (
                <div key={r.k} className="fact-row" data-ok={!!okLines[r.k]} data-ask={r.ask ? "true" : undefined}>
                  <dt>{r.label}</dt>
                  <dd>
                    {r.value}
                    {r.ask ? (
                      <>
                        <span className="fact-ask">{r.ask}</span>
                        <span className="fact-ask-hint">{C.howManyHint}</span>
                      </>
                    ) : null}
                  </dd>
                  <span className="fact-actions">
                    <button
                      type="button"
                      className="fact-ok"
                      aria-pressed={!!okLines[r.k]}
                      aria-label={`${r.label}: ${t("confirm.yes")}`}
                      onClick={() => setOkLines((o) => ({ ...o, [r.k]: !o[r.k] }))}
                    >
                      <CheckIcon />
                    </button>
                    <button type="button" className="fact-fix" onClick={flow.no} disabled={flow.phase === "saving"} aria-label={`${r.label}: ${t("speak.fix")}`}>
                      <PenIcon />
                      <span>{t("speak.fix")}</span>
                    </button>
                  </span>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        {items.length ? (
          <div className="receipt-section">
            <p className="eyebrow">{C.how}</p>
            <ol className="items receipt-items">
              {items.map((it, i) => (
                <li
                  key={`${it.kind}-${it.month}-${i}`}
                  className="item"
                  data-kind={it.kind}
                  data-included={it.included_in_total || (flow.includeShortfall && it.kind === "min_wage_shortfall")}
                >
                  <span className="item-no" aria-hidden="true">
                    {i + 1}
                  </span>
                  <div className="item-body">
                    <div className="item-row">
                      <span className="item-label" title={it.label}>
                        {itemLabel(t, it, lang)} {it.is_estimate ? <EstimateTag t={t} /> : null}
                      </span>
                      {/* money already received (paid_received) comes off the total: "− ₹X", not owed */}
                      {it.amount < 0 ? (
                        <span className="money" data-sign="neg">
                          − {inr(-it.amount)}
                        </span>
                      ) : (
                        <Money value={it.amount} />
                      )}
                    </div>
                    {it.note ? <p className="meta">{it.note}</p> : null}
                    {/* lines with no source (money already received) have nothing to open */}
                    {it.source ? (
                      <details className="item-source">
                        <summary>{t("common.source")}</summary>
                        <p className="meta">{it.label}</p>
                        <p>{it.source}</p>
                      </details>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        <div className="receipt-total">
          <span>{t("confirm.total")}</span>
          <span className="money">{inr(flow.total)}</span>
        </div>
        <Sources items={calc?.sources ?? []} title={t("common.sources")} />
      </section>

      {haq ? (
        <section className="card haq" aria-label={t("confirm.haq_title")}>
          <div className="haq-head">
            <h2 className="card-title">{t("confirm.haq_title")}</h2>
            <StatusPill tone="estimate" className="pill-lg">
              {t("common.estimate")}
            </StatusPill>
          </div>
          {flow.hasShortfall ? (
            <>
              <p>
                {t("confirm.haq_text")}: <Money value={haq.minimum_for_hours ?? 0} />
              </p>
              <p className="haq-gap">
                {t("confirm.haq_gap")}: <Money value={haq.monthly_gap ?? 0} /> · {inr(flow.shortfallTotal)}
              </p>
              <Toggle checked={flow.includeShortfall} onChange={(v) => void flow.toggleShortfall(v)} label={t("confirm.haq_include")} />
            </>
          ) : (
            <p>{t("confirm.haq_none")}</p>
          )}
          <p className="haq-law">
            <span className="haq-law-tag">{C.law}</span>
            <span>{t("confirm.haq_source")}</span>
          </p>
          <details className="item-source">
            <summary>
              {t("common.source")}: {t("confirm.haq_source")}
            </summary>
            <p>{haq.source}</p>
            <p className="meta">{haq.basis}</p>
            <p className="meta">{haq.vda_note}</p>
          </details>
        </section>
      ) : null}

      {flow.warnings.length ? (
        <div className="warning-note">
          <p>{t("confirm.warning")}:</p>
          <ul>
            {flow.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {calc?.disclaimer ? <p className="footnote">{calc.disclaimer}</p> : null}

      <ErrorNote message={flow.error} />
      <div className="yes-no">
        <button type="button" className="btn btn-yes btn-big" onClick={() => void onYes()} disabled={flow.phase === "saving"}>
          {flow.phase === "saving" ? t("confirm.saving") : t("confirm.yes")}
        </button>
        <button type="button" className="btn btn-no btn-big" onClick={flow.no} disabled={flow.phase === "saving"}>
          {t("confirm.no")}
        </button>
      </div>
    </div>
  );
}

export function ConfirmScreen() {
  const { t } = useT();
  const hydrated = useHydrated();
  return (
    <Screen title={t("confirm.title")} back="/speak" t={t} className="confirm-screen">
      {hydrated ? <ConfirmFlow /> : <Loading label={t("common.loading")} />}
    </Screen>
  );
}
