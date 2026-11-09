"use client";

// Worker home (/): totals, one card per home, a big mic, and a hidden demo menu.

import Link from "next/link";
import { useDashboard, useSettings, useT } from "@/hooks";
import { UI_LANGS, type StringKey } from "@/lib/i18n";
import { inr, shortDate } from "@/lib/format";
import { EstimateTag, ErrorNote, Loading, Money, Screen } from "@/components/ui/primitives";
import { MicIcon } from "@/components/ui/icons";

export function LanguagePicker({ onPick, title }: { onPick: (l: (typeof UI_LANGS)[number]["value"]) => void; title: string }) {
  return (
    <section className="lang-picker" aria-label={title}>
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
  return (
    <Screen title={dash.worker ? `${t("app.name")} · ${dash.worker.name}` : t("app.name")} t={t}>
      <section className="totals" aria-label={t("home.total_baaki")}>
        <div className="total-main">
          <p className="total-label">{t("home.total_baaki")}</p>
          <p className="total-value">{inr(totals?.baaki ?? 0)}</p>
        </div>
        <dl className="total-row">
          <div>
            <dt>{t("home.recovered")}</dt>
            <dd>
              <Money value={totals?.recovered ?? 0} />
            </dd>
          </div>
          <div>
            <dt>
              {t("home.hidden")} <EstimateTag t={t} />
            </dt>
            <dd>
              <Money value={totals?.hidden_baaki_estimate ?? 0} />
            </dd>
          </div>
          <div>
            <dt>{t("home.homes")}</dt>
            <dd>{totals?.homes ?? 0}</dd>
          </div>
        </dl>
      </section>

      <Link href="/speak" className="mic-link" aria-label={t("home.speak")}>
        <span className="mic" data-state="idle">
          <MicIcon />
        </span>
        <span className="mic-link-label">{t("home.speak")}</span>
        <span className="hint">{t("home.speak_hint")}</span>
      </Link>

      {dash.loading ? <Loading label={t("common.loading")} /> : null}
      <ErrorNote message={dash.error} onRetry={dash.refresh} retryLabel={t("common.retry")} />

      <section aria-label={t("home.title")}>
        <h2 className="section-title">{t("home.title")}</h2>
        {!dash.loading && dash.cards.length === 0 && !dash.error ? <p className="muted">{t("home.empty")}</p> : null}
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
            </li>
          ))}
        </ul>
      </section>

      <nav className="quick-nav" aria-label="More">
        <Link href="/diary" className="btn">
          {t("home.diary")}
        </Link>
        <Link href="/voice" className="btn">
          {t("home.voice")}
        </Link>
        <Link href="/safety" className="btn">
          {t("home.safety")}
        </Link>
      </nav>

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
