"use client";

// /dues: "people who owe you", grouped by kind, with totals and broken-promise counts. Hero: the total owed,
// counting up, and one dot per promise not kept. `asOf` (?as_of=YYYY-MM-DD) shifts "today" for the demo.

import { useCallback, useEffect, useState } from "react";
import { Card, CountUp, ErrorNote, GradientButton, Screen, SkeletonCard, StatusPill } from "@/components/ui/primitives";
import { useT } from "@/hooks";
import { inr } from "@/lib/format";
import { duesLang, listDues, loadDemo, type DuesKind, type DuesList, type DuesSummary } from "@/lib/features/dues";
import { DuesArt } from "./DuesArt";
import { NotAdvice, initial } from "./parts";
import { duesStrings, type DuesStrings } from "./strings";
import css from "./dues.module.css";

const ORDER: DuesKind[] = ["vendor", "chit", "other"];

export function DuesListScreen({ asOf }: { asOf?: string | null }) {
  const { t, lang } = useT();
  const S = duesStrings(lang);
  const [data, setData] = useState<DuesList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [demoBusy, setDemoBusy] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setData(await listDues(asOf, signal));
        setError(null);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(S.error);
      } finally {
        setLoading(false);
      }
    },
    [asOf, S.error],
  );

  useEffect(() => {
    const ac = new AbortController();
    // load() sets state only after its fetch resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(ac.signal);
    return () => ac.abort();
  }, [load]);

  async function demo() {
    setDemoBusy(true);
    try {
      await loadDemo();
      await load();
    } catch {
      setError(S.error);
    } finally {
      setDemoBusy(false);
    }
  }

  const people = data?.accounts.length ?? 0;
  return (
    <Screen title={S.title} back="/app" t={t}>
      {loading && !data ? (
        <div role="status" aria-label={t("common.loading")} className="stack">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}
      {!data && !loading ? <ErrorNote message={error} onRetry={() => void load()} retryLabel={S.retry} /> : null}

      {data ? (
        <>
          <Card tone="glow" className={`${css.hero} ${css.rise}`}>
            <p className={css.eyebrow}>{S.heroLabel}</p>
            <p className={css.big} aria-live="polite">
              <CountUp value={data.total} />
            </p>
            <p className={css.sub}>{S.heroSub(people, data.promises_broken)}</p>
            {data.promises_broken ? (
              <div className={css.dots} aria-hidden="true">
                {Array.from({ length: Math.min(data.promises_broken, 24) }).map((_, i) => (
                  <span key={i} className={css.dot} data-status="broken" style={{ animationDelay: `${300 + i * 80}ms` }} />
                ))}
              </div>
            ) : null}
          </Card>

          <GradientButton href="/dues/new">{S.add}</GradientButton>

          {people === 0 ? (
            <div className="stack" style={{ justifyItems: "center", textAlign: "center" }}>
              <div style={{ display: "flex", gap: 8 }}>
                {ORDER.map((k) => (
                  <DuesArt key={k} kind={k} size={84} />
                ))}
              </div>
              <p className="section-title">{S.empty}</p>
              <p className="hint">{S.emptyHint}</p>
              <button type="button" className="btn" onClick={() => void demo()} disabled={demoBusy}>
                {demoBusy ? S.demoLoading : S.demo}
              </button>
            </div>
          ) : null}

          {ORDER.map((k) => {
            const rows = data.accounts.filter((a) => a.kind === k);
            if (!rows.length) return null;
            return (
              <section key={k} className={css.section} aria-label={S.kinds[k]}>
                <div className={css.sectionHead}>
                  <h2 className="section-title">{S.kinds[k]}</h2>
                  <span className={css.sectionTotal}>{inr(data.by_kind[k].balance)}</span>
                </div>
                <ul className={css.list}>
                  {rows.map((a, i) => (
                    <li key={a.id} className={css.rise} style={{ animationDelay: `${i * 60}ms` }}>
                      <PersonRow a={a} S={S} lang={lang} asOf={asOf} />
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}

          {people > 0 ? (
            <button type="button" className="btn btn-ghost" onClick={() => void demo()} disabled={demoBusy}>
              {demoBusy ? S.demoLoading : S.demo}
            </button>
          ) : null}
          <NotAdvice S={S} />
        </>
      ) : null}
    </Screen>
  );
}

function PersonRow({ a, S, lang, asOf }: { a: DuesSummary; S: DuesStrings; lang: ReturnType<typeof useT>["lang"]; asOf?: string | null }) {
  const dl = duesLang(lang);
  const what = a.item_labels.map((l) => l[dl]).join(" · ") || a.title;
  const href = `/dues/${a.id}${asOf ? `?as_of=${asOf}` : ""}`;
  return (
    <Card href={href} className={css.row}>
      <span className={`${css.avatar} ${css.avatarSm}`} aria-hidden="true">
        {initial(a.party_name)}
      </span>
      <span className={css.rowMain}>
        <span className={css.rowName}>{a.party_display[dl] || a.party_name}</span>
        <span className={css.rowWhat}>{what}</span>
      </span>
      <span className={css.rowRight}>
        <span className={css.money}>{a.balance_display}</span>
      </span>
      {a.promises_made ? (
        <span className={css.rowFoot}>
          <StatusPill tone={a.promises_broken ? "error" : "accent"}>{S.promisedTimes(a.promises_made, a.promises_broken)}</StatusPill>
          <span className="hint">{S.since(a.months_ago)}</span>
          {a.pack_eligible ? <StatusPill tone="warn" dot={false}>{S.packReady}</StatusPill> : null}
        </span>
      ) : null}
    </Card>
  );
}
