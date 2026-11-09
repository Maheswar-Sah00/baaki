"use client";

// Confirm (/case/new): which home → facts + calculation with sources + read-back → ✓ Haan / ✗ Nahi.
// Also used by the Case screen to finish a case that is still a draft (resumeCaseId).

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAudioPlayer, useDashboard, useHydrated, useNewCase, useSafety, useSettings, useT, type HomeChoice } from "@/hooks";
import { inr, itemLabel } from "@/lib/format";
import type { Employer, LangCode } from "@/lib/types";
import { ErrorNote, EstimateTag, Loading, Money, PlayButton, Screen, Sources, Toggle } from "@/components/ui/primitives";

const EMPLOYER_LANGS: { value: LangCode; label: string }[] = [
  { value: "hi-en", label: "Hinglish" },
  { value: "te-IN", label: "తెలుగు" },
  { value: "en-IN", label: "English" },
];

export function ConfirmFlow({ resumeCaseId = null, onConfirmed }: { resumeCaseId?: number | null; onConfirmed?: (id: number) => void }) {
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

  if (flow.phase === "extracting" || flow.phase === "creating" || (!flow.caseData && flow.phase === "saving")) {
    return <Loading label={t("confirm.reading")} />;
  }

  if (flow.phase === "error") {
    return (
      <div className="stack">
        <ErrorNote message={flow.error === "nothing_said" ? t("speak.tap") : flow.error} />
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
                {e.name}
                {e.locality ? <span className="muted"> · {e.locality}</span> : null}
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
              + {t("confirm.new_home")}
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
        <button type="button" className="btn btn-primary btn-big" onClick={() => void flow.chooseHome()} disabled={!choice}>
          {t("confirm.use_this")}
        </button>
      </section>
    );
  }

  // ------------------------------------------------------------------ review (read-back gate)
  const f = flow.facts;
  const calc = flow.calc;
  const items = calc?.items ?? [];
  const audioUrl = flow.readbackAudioUrl;
  const haq = flow.haq;

  const onYes = async () => {
    const id = await flow.yes();
    if (id === null) return;
    if (onConfirmed) onConfirmed(id);
    else router.replace(`/case/${id}`);
  };

  return (
    <div className="stack confirm-review">
      <section className="card readback" aria-live="polite">
        <h2 className="card-title">{t("confirm.title")}</h2>
        <ol className="readback-lines">
          {flow.readbackSentences.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
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
      </section>

      <section className="total-box">
        <p className="total-label">{t("confirm.total")}</p>
        <p className="total-value">{inr(flow.total)}</p>
        {flow.draft.summary && flow.draft.summary.total !== flow.total ? (
          <p className="meta">
            {t("confirm.you_said")}: {inr(flow.draft.summary.total)}
          </p>
        ) : null}
      </section>

      {f ? (
        <dl className="facts">
          <div>
            <dt>{t("confirm.employer")}</dt>
            <dd>{flow.caseData?.employer?.name ?? (f.employer_name as string) ?? "—"}</dd>
          </div>
          <div>
            <dt>{t("confirm.wage")}</dt>
            <dd>
              <Money value={Number(f.monthly_wage ?? 0)} />
            </dd>
          </div>
          <div>
            <dt>{t("confirm.months")}</dt>
            <dd>{flow.caseData?.months_unpaid ?? f.months_unpaid ?? "—"}</dd>
          </div>
          {f.hours_per_day ? (
            <div>
              <dt>{t("confirm.hours")}</dt>
              <dd>{f.hours_per_day}</dd>
            </div>
          ) : null}
          {f.deductions?.length ? (
            <div>
              <dt>{t("confirm.cuts")}</dt>
              <dd>{f.deductions.map((d) => inr(d.amount)).join(", ")}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {items.length ? (
        <ul className="items">
          {items.map((it, i) => (
            <li key={`${it.kind}-${it.month}-${i}`} className="item" data-kind={it.kind} data-included={it.included_in_total || (flow.includeShortfall && it.kind === "min_wage_shortfall")}>
              <div className="item-row">
                <span className="item-label" title={it.label}>
                  {itemLabel(t, it, lang)} {it.is_estimate ? <EstimateTag t={t} /> : null}
                </span>
                <Money value={it.amount} />
              </div>
              {it.note ? <p className="meta">{it.note}</p> : null}
              <details className="item-source">
                <summary>{t("common.source")}</summary>
                <p className="meta">{it.label}</p>
                <p>{it.source}</p>
              </details>
            </li>
          ))}
        </ul>
      ) : null}

      {haq ? (
        <section className="card haq" aria-label={t("confirm.haq_title")}>
          <h2 className="card-title">
            {t("confirm.haq_title")} <EstimateTag t={t} />
          </h2>
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

      <Sources items={calc?.sources ?? []} title={t("common.sources")} />
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
