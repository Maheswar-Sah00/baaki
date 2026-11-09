"use client";

// Worker home (/app): totals, a map of her homes, a big glowing mic, one card per home, the bottom
// nav and a hidden demo menu. The marketing website is at "/".

import Link from "next/link";
import { useDashboard, useSettings, useT } from "@/hooks";
import { UI_LANGS, type StringKey } from "@/lib/i18n";
import { inr, shortDate } from "@/lib/format";
import {
  EstimateTag,
  ErrorNote,
  GlowRing,
  HomesMap,
  Illustration,
  Loading,
  Money,
  Screen,
  SkeletonCard,
  toneForState,
} from "@/components/ui/primitives";
import { MicIcon } from "@/components/ui/icons";
import { ExitLink } from "@/components/features/exit/ExitLink";
import { DuesEntryCard } from "@/components/features/dues/parts";

export function LanguagePicker({ onPick, title }: { onPick: (l: (typeof UI_LANGS)[number]["value"]) => void; title: string }) {
  return (
    <section className="lang-picker" aria-label={title}>
      <Illustration name="speak" animated size={240} style={{ margin: "0 auto 8px" }} />
      <h2 className="section-title">{title}</h2>
      <div className="stack">
        {UI_LANGS.map((l) => (
          <button key={l.value} type="button" className="btn btn-big" onClick={() => onPick(l.value)}>
            {l.label}
          </button>
        ))}
      </div>
    </section>
  );
}

export function HomeScreen() {
  const settings = useSettings();
  const { t, lang } = useT();
  const dash = useDashboard(settings.hydrated ? settings.workerId : null);

  if (!settings.hydrated) {
    return (
      <Screen safetyLink={false}>
        <Loading label={t("common.loading")} />
      </Screen>
    );
  }

  if (settings.needsLanguage) {
    return (
      <Screen title={t("app.name")} safetyLink={false}>
        <LanguagePicker title={`${t("lang.pick")} · భాష · भाषा`} onPick={settings.setUiLang} />
      </Screen>
    );
  }

  const totals = dash.totals;
  // Yearly underpayment estimate: haq_check.monthly_gap is a per-month figure (legal minimum for her
  // hours minus the agreed wage), so x12 gives a year. totals.hidden_baaki_estimate is NOT monthly
  // (it sums the gap over the months on record), so it is shown as is, as "so far".
  const hiddenMonthly = dash.cards.reduce((sum, c) => sum + (c.haq_check?.monthly_gap ?? 0), 0);
  const hiddenYear = hiddenMonthly * 12;
  return (
    <Screen title={dash.worker ? `${t("app.name")} · ${dash.worker.name}` : t("app.name")} t={t} nav="home">
      <section className="totals totals-outcome" aria-label={t("home.total_baaki")}>
        <p className="totals-tagline">{t("home.tagline")}</p>
        <div className="total-main">
          <p className="total-label">{t("home.total_baaki")}</p>
          <p className="total-value">{inr(totals?.baaki ?? 0)}</p>
        </div>
        <div className="total-hidden-year" data-empty={hiddenYear > 0 ? undefined : "true"}>
          <p className="total-hidden-label">
            {t("home.hidden_year")} <EstimateTag t={t} />
          </p>
          <p className="total-hidden-value">
            <Money value={hiddenYear} />
          </p>
          <p className="total-hidden-hint">
            {t("home.hidden_year_hint")}
            {totals?.hidden_baaki_estimate ? ` · ${t("home.hidden_so_far", { amount: inr(totals.hidden_baaki_estimate) })}` : ""}
          </p>
        </div>
        <dl className="total-row total-row-2">
          <div>
            <dt>{t("home.recovered")}</dt>
            <dd className="total-recovered">
              <Money value={totals?.recovered ?? 0} />
            </dd>
          </div>
          <div>
            <dt>{t("home.homes")}</dt>
            <dd>{totals?.homes ?? 0}</dd>
          </div>
        </dl>
      </section>

      <Link href="/speak" className="mic-link" aria-label={t("home.speak")}>
        <GlowRing>
          <span className="mic" data-state="idle">
            <MicIcon />
          </span>
        </GlowRing>
        <span className="mic-link-label">{t("home.speak")}</span>
        <span className="hint">{t("home.speak_hint")}</span>
      </Link>

      {/* RAISE MOUNT: the main session mounts <RaiseCard workerId={settings.workerId} /> here (Haq Raise:
          ask for a raise to the legal minimum; links to /raise/{case}). Built in components/features/raise. */}

      {dash.loading && dash.cards.length === 0 ? (
        <div className="stack" role="status" aria-label={t("common.loading")}>
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : dash.loading ? (
        <Loading label={t("common.loading")} />
      ) : null}
      <ErrorNote message={dash.error} onRetry={dash.refresh} retryLabel={t("common.retry")} />

      <section aria-label={t("home.title")}>
        <h2 className="section-title">{t("home.title")}</h2>
        {!dash.loading && dash.cards.length === 0 && !dash.error ? (
          <div className="home-empty">
            <Illustration name="empty" size={200} />
            <p className="muted">{t("home.empty")}</p>
          </div>
        ) : null}
        {dash.cards.length > 0 ? (
          <HomesMap
            className="home-map"
            label={t("home.title")}
            you={dash.worker?.name ?? t("app.name")}
            homes={dash.cards.map((c) => ({
              id: c.case_id,
              name: c.employer?.name ?? "—",
              amount: c.balance,
              tone: toneForState(c.state),
              href: `/case/${c.case_id}`,
            }))}
          />
        ) : null}
        <ul className="cards">
          {dash.cards.map((c) => (
            <li key={c.case_id}>
              <Link href={`/case/${c.case_id}`} className="card home-card" data-state={c.state}>
                <div className="home-card-head">
                  <span className="home-card-name">{c.employer?.name ?? "—"}</span>
                  <span className="tag" data-state={c.state}>
                    {t(`state.${c.state}` as StringKey)}
                  </span>
                </div>
                <p className="home-card-balance">
                  <span className="muted">{t("home.balance")}</span> <Money value={c.balance} />
                </p>
                {c.shortfall_estimate > 0 ? (
                  <p className="home-card-hidden">
                    {t("home.hidden")}: <Money value={c.shortfall_estimate} /> <EstimateTag t={t} />
                  </p>
                ) : null}
                {c.last_step ? (
                  <p className="meta">
                    {t("home.last_step")}: {t(`case.step.${c.last_step}` as StringKey)} · {shortDate(c.last_sent_at, lang)}
                  </p>
                ) : null}
                {c.next_reminder ? (
                  <p className="meta">
                    {t("home.next_reminder")}: {shortDate(c.next_reminder, lang)}
                  </p>
                ) : null}
                {c.fair_employer ? <span className="badge badge-fair">{t("home.fair")}</span> : null}
              </Link>
              <ExitLink employerId={c.employer?.id} caseId={c.case_id} variant="text" />
            </li>
          ))}
        </ul>
      </section>

      <DuesEntryCard />

      <details className="dev-menu">
        <summary aria-label={t("home.dev")}>·</summary>
        <div className="stack">
          <p className="meta">{t("home.dev")}</p>
          <div className="row">
            <span className="muted">{t("lang.change")}:</span>
            {UI_LANGS.map((l) => (
              <button key={l.value} type="button" className="btn btn-small" aria-pressed={settings.uiLang === l.value} onClick={() => settings.setUiLang(l.value)}>
                {l.label}
              </button>
            ))}
          </div>
          <div className="row">
            <span className="muted">{t("home.worker")}:</span>
            <button
              type="button"
              className="btn btn-small"
              aria-pressed={settings.workerId === (dash.resetResult?.workers.lakshmi ?? 1)}
              onClick={() => settings.update({ workerId: dash.resetResult?.workers.lakshmi ?? 1, uiLang: "te" })}
            >
              Lakshmi · తెలుగు
            </button>
            <button
              type="button"
              className="btn btn-small"
              aria-pressed={settings.workerId === (dash.resetResult?.workers.rafiq ?? 2)}
              onClick={() => settings.update({ workerId: dash.resetResult?.workers.rafiq ?? 2, uiLang: "hi-en" })}
            >
              Rafiq · Hinglish
            </button>
          </div>
          <button type="button" className="btn" disabled={dash.resetting} onClick={() => void dash.reset()}>
            {dash.resetting ? t("common.loading") : t("home.reset")}
          </button>
          {dash.resetResult ? <p className="meta">{t("home.reset_done")}</p> : null}
          <ErrorNote message={dash.resetError} />
          {dash.cards.length ? (
            <ul className="plain-list">
              {dash.cards.map((c) => (
                <li key={c.case_id}>
                  <Link href={c.employer_path}>
                    {c.employer?.name}: {c.employer_path}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="footnote">{t("common.not_legal_advice")}</p>
        </div>
      </details>
    </Screen>
  );
}
