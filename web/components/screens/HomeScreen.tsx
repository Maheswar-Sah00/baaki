"use client";

// Worker home (/app): a calm wallet for the money owed to her. Greeting, the big "money still owed"
// figure (counts up), one primary action (Tell Baaki), her tools as pale tiles, a paper map + list
// of her homes, recent activity, and the hidden demo menu. The marketing website is at "/".

import Link from "next/link";
import type { ReactNode } from "react";
import { useDashboard, useSettings, useT } from "@/hooks";
import { UI_LANGS, translator, type StringKey, type UiLang } from "@/lib/i18n";
import { inr, shortDate } from "@/lib/format";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { LogoMark } from "@/components/ui/Logo";
import {
  ErrorNote,
  EstimateTag,
  GlowRing,
  HomesMap,
  Illustration,
  Loading,
  Money,
  MoneyFigure,
  Screen,
  SkeletonCard,
  StatusPill,
  avatarTone,
  toneForState,
} from "@/components/ui/primitives";
import {
  ArrowRightIcon,
  ChevronRightIcon,
  ClockIcon,
  DiaryIcon,
  DoorIcon,
  InboxIcon,
  MicIcon,
  ShieldIcon,
  TrendUpIcon,
  WalletIcon,
} from "@/components/ui/icons";
import { ExitLink } from "@/components/features/exit/ExitLink";
import { RaiseCard } from "@/components/features/raise/RaiseCard";

// Hub-only labels (short tile names, greeting). Kept here so the shared i18n table stays untouched.
type HubLabels = {
  greet: string;
  tools: string;
  recent: string;
  dues: string;
  inbox: string;
  raise: string;
  exit: string;
  claim: (employer: string, amount: string) => string;
  claimCta: string;
  draft: (employer: string, amount: string) => string;
  draftGo: string;
};
const HUB: Record<UiLang, HubLabels> = {
  en: {
    greet: "Namaste",
    tools: "Your tools",
    recent: "Recent",
    dues: "Other dues",
    inbox: "Replies",
    raise: "Ask a raise",
    exit: "Asked to leave",
    claim: (e, a) => `${e} says ${a} was paid. Did it arrive?`,
    claimCta: "Check",
    draft: (e, a) => `Not finished: ${e} ${a}`,
    draftGo: "Continue",
  },
  "hi-en": {
    greet: "Namaste",
    tools: "Aapke tools",
    recent: "Haal mein",
    dues: "Udhaar",
    inbox: "Jawab",
    raise: "Salary badhao",
    exit: "Kaam se nikala",
    claim: (e, a) => `${e} कहते हैं ${a} दे दिए। पैसे मिले?`,
    claimCta: "देखिए",
    draft: (e, a) => `अधूरा: ${e} ${a}`,
    draftGo: "आगे बढ़िए",
  },
  te: {
    greet: "నమస్తే",
    tools: "మీ సాధనాలు",
    recent: "ఇటీవల",
    dues: "ఇతర బాకీలు",
    inbox: "జవాబులు",
    raise: "జీతం పెంపు",
    exit: "పని నుంచి తీసేశారు",
    claim: (e, a) => `${a} ఇచ్చామని ${e} చెప్పారు. డబ్బులు అందాయా?`,
    claimCta: "చూడండి",
    draft: (e, a) => `పూర్తి కాలేదు: ${e} ${a}`,
    draftGo: "కొనసాగించండి",
  },
};

const LANG_SUB: Record<UiLang, string> = { te: "Telugu", "hi-en": "Hindi · Hinglish", en: "English" };
const LOCALE: Record<UiLang, string> = { te: "te-IN", "hi-en": "hi-IN", en: "en-IN" };
type TileTone = "sky" | "peach" | "lilac" | "sage" | "butter" | "rose";

export function LanguagePicker({ onPick, title }: { onPick: (l: (typeof UI_LANGS)[number]["value"]) => void; title: string }) {
  return (
    <section className="lang-picker" aria-label={title}>
      {/* Lakshmi waving with three speech bubbles (Telugu / Hindi / English); her waist is the cut edge,
          so she stands flush on the panel's bottom edge. Missing file: the inline speak illustration. */}
      <div className="lang-hero-wrap">
        <AssetSlot
          name="app-welcome"
          alt="A domestic worker waving hello, with speech bubbles in Telugu, Hindi and English"
          ratio="16/11"
          tone="peach"
          fit="contain"
          anchor="bottom"
          priority
          className="lang-hero"
          fallback={<Illustration name="speak" animated />}
        />
      </div>
      <div className="lang-copy">
        <p className="eyebrow">
          Baaki · <span lang="te">బాకీ</span>
        </p>
        <h1 className="lang-title">
          Say what you&rsquo;re <em className="accent">owed.</em>
        </h1>
        <p className="lang-sub">
          <span lang="te">{translator("te")("app.tagline")}</span>
          <span lang="hi">{translator("hi-en")("home.tagline")}</span>
        </p>
      </div>
      <h2 className="lang-pick-title">{title}</h2>
      <div className="lang-list">
        {UI_LANGS.map((l) => (
          <button key={l.value} type="button" className="lang-option" onClick={() => onPick(l.value)}>
            <span className="lang-option-native" lang={l.value === "te" ? "te" : l.value === "hi-en" ? "hi" : "en"}>
              {l.label}
            </span>
            {l.value !== "en" ? <span className="lang-option-sub">{LANG_SUB[l.value]}</span> : null}
            <ChevronRightIcon className="lang-option-arrow" />
          </button>
        ))}
      </div>
    </section>
  );
}

function Tile({ href, icon, label, tone }: { href: string; icon: ReactNode; label: string; tone: TileTone }) {
  return (
    <Link href={href} className="hub-tile" data-tone={tone}>
      <span className="hub-tile-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="hub-tile-label">{label}</span>
    </Link>
  );
}

export function HomeScreen() {
  const settings = useSettings();
  const { t, lang } = useT();
  const dash = useDashboard(settings.hydrated ? settings.workerId : null);
  const H = HUB[lang];

  if (!settings.hydrated) {
    return (
      <Screen safetyLink={false}>
        <Loading label={t("common.loading")} />
      </Screen>
    );
  }

  if (settings.needsLanguage) {
    return (
      <Screen safetyLink={false} className="lang-screen" left={<Brand />}>
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
  const name = dash.worker?.name ?? "";
  const firstCase = dash.owing[0]?.case_id ?? dash.cards[0]?.case_id ?? null;
  const today = new Date().toLocaleDateString(LOCALE[lang], { weekday: "short", day: "numeric", month: "short" });

  // Recent activity, newest first: what was sent, what is due next, and each home's state.
  type Act = { key: string; caseId: number; who: string; text: string; when: string; sort: number; tone: ReturnType<typeof toneForState>; icon: "sent" | "clock" | "state" };
  const acts: Act[] = [];
  for (const c of dash.cards) {
    const who = c.employer?.name ?? "—";
    if (c.last_step) {
      acts.push({
        key: `s${c.case_id}`,
        caseId: c.case_id,
        who,
        text: `${t("home.last_step")}: ${t(`case.step.${c.last_step}` as StringKey)}`,
        when: shortDate(c.last_sent_at, lang),
        sort: c.last_sent_at ? Date.parse(c.last_sent_at) : 0,
        tone: "success",
        icon: "sent",
      });
    }
    if (c.next_reminder) {
      acts.push({
        key: `r${c.case_id}`,
        caseId: c.case_id,
        who,
        text: t("home.next_reminder"),
        when: shortDate(c.next_reminder, lang),
        sort: Date.parse(c.next_reminder) || 0,
        tone: "neutral",
        icon: "clock",
      });
    }
    if (!c.last_step) {
      acts.push({
        key: `t${c.case_id}`,
        caseId: c.case_id,
        who,
        text: t(`state.${c.state}` as StringKey),
        when: c.balance > 0 ? inr(c.balance) : "",
        sort: -c.case_id,
        tone: toneForState(c.state),
        icon: "state",
      });
    }
  }
  acts.sort((a, b) => b.sort - a.sort);

  return (
    <Screen t={t} nav="home" left={<Brand />} className="hub-screen">
      <header className="hub-greeting">
        <p className="eyebrow">
          {today}
          {dash.worker?.city ? ` · ${dash.worker.city}` : ""}
        </p>
        <h1 className="hub-hello">
          {H.greet}
          {name ? (
            <>
              , <em className="accent">{name}</em>
            </>
          ) : null}
        </h1>
        <p className="hub-tagline">{t("home.tagline")}</p>
      </header>

      <section className="totals totals-outcome hub-wallet" aria-label={t("home.total_baaki")}>
        <div className="hub-wallet-top">
          <p className="total-label">{t("home.total_baaki")}</p>
          <StatusPill tone="neutral" dot={false}>
            {totals?.homes ?? 0} · {t("home.homes")}
          </StatusPill>
        </div>
        <p className="total-value hub-wallet-figure">
          <MoneyFigure value={totals?.baaki ?? 0} count size="xl" />
        </p>
        <dl className="total-row hub-wallet-stats">
          <div>
            <dt>{t("home.recovered")}</dt>
            <dd className="total-recovered" data-zero={!(totals?.recovered ?? 0)}>
              <Money value={totals?.recovered ?? 0} />
            </dd>
          </div>
        </dl>
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
      </section>

      {/* The one primary action. Lakshmi (ill-speak) rises from the card's bottom edge on the right;
          the ink mic stays the strongest thing in the card. */}
      <Link href="/speak" className="mic-link hub-speak" aria-label={t("home.speak")}>
        <span className="hub-speak-text">
          <span className="mic-link-label">{t("home.speak")}</span>
          <span className="hint">{t("home.speak_hint")}</span>
        </span>
        <GlowRing>
          <span className="mic" data-state="idle">
            <MicIcon />
          </span>
        </GlowRing>
        <Illustration name="speak" className="hub-speak-art" />
      </Link>

      {/* Haq Raise: ask for a raise to the legal minimum; links to /raise/{case}. */}
      {settings.hydrated ? <RaiseCard workerId={settings.workerId} /> : null}

      <section aria-label={H.tools} className="hub-tools">
        <h2 className="section-title">{H.tools}</h2>
        <div className="hub-tiles">
          <Tile href="/dues" icon={<WalletIcon />} label={H.dues} tone="butter" />
          {firstCase ? <Tile href={`/inbox/${firstCase}`} icon={<InboxIcon />} label={H.inbox} tone="sky" /> : null}
          {firstCase ? <Tile href={`/raise/${firstCase}`} icon={<TrendUpIcon />} label={H.raise} tone="sage" /> : null}
          <Tile href="/exit" icon={<DoorIcon />} label={H.exit} tone="peach" />
          <Tile href="/diary" icon={<DiaryIcon />} label={t("home.diary")} tone="lilac" />
          <Tile href="/safety" icon={<ShieldIcon />} label={t("home.safety")} tone="rose" />
        </div>
      </section>

      {dash.loading && dash.cards.length === 0 ? (
        <div className="stack" role="status" aria-label={t("common.loading")}>
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : dash.loading ? (
        <Loading label={t("common.loading")} />
      ) : null}
      <ErrorNote message={dash.error} onRetry={dash.refresh} retryLabel={t("common.retry")} />

      <section aria-label={t("home.title")} className="hub-homes">
        <div className="hub-section-head">
          <h2 className="section-title">{t("home.title")}</h2>
          {dash.cards.length ? <span className="hub-count">{dash.cards.length}</span> : null}
        </div>
        {!dash.loading && dash.cards.length === 0 && !dash.error ? (
          <div className="home-empty">
            <AssetSlot
              name="app-empty-homes"
              alt="A quiet doorway of a Hyderabad apartment"
              ratio="16/9"
              tone="sky"
              fit="contain"
              fallback={<Illustration name="empty" />}
            />
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
        <ul className="cards hub-home-list">
          {dash.cards.map((c) => {
            const ename = c.employer?.name ?? "—";
            return (
              <li key={c.case_id} className="hub-home">
                {(c.pending_claims ?? 0) > 0 ? (
                  <Link href={`/hisaab/${c.case_id}`} className="claim-card claim-card-inline">
                    <span className="claim-card-icon" aria-hidden="true">
                      <span className="claim-card-dot" />
                    </span>
                    <span className="claim-card-text">{H.claim(ename, inr(c.pending_claims_amount ?? 0))}</span>
                    <span className="claim-card-cta">
                      {H.claimCta} <ArrowRightIcon />
                    </span>
                  </Link>
                ) : null}
                <Link href={`/case/${c.case_id}`} className="card home-card" data-state={c.state}>
                  <span className="hub-avatar" data-tone={avatarTone(ename)} aria-hidden="true">
                    {Array.from(ename)[0]?.toUpperCase()}
                  </span>
                  <span className="home-card-main">
                    <span className="home-card-head">
                      <span className="home-card-name">{ename}</span>
                      {c.employer?.locality ? <span className="home-card-place">{c.employer.locality}</span> : null}
                    </span>
                    <span className="home-card-tags">
                      <span className="tag" data-state={c.state}>
                        {t(`state.${c.state}` as StringKey)}
                      </span>
                      {c.fair_employer ? <span className="badge badge-fair">{t("home.fair")}</span> : null}
                    </span>
                  </span>
                  <span className="home-card-balance">
                    <span className="home-card-owed">{t("home.balance")}</span>
                    <Money value={c.balance} />
                  </span>
                  <ChevronRightIcon className="home-card-arrow" />
                </Link>
                {c.shortfall_estimate > 0 || c.last_step || c.next_reminder ? (
                  <div className="home-card-meta">
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
                  </div>
                ) : null}
                <div className="home-card-foot">
                  <ExitLink employerId={c.employer?.id} caseId={c.case_id} variant="text" />
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      {/* cases she started but never confirmed (not in the totals): continue where she stopped */}
      {dash.dashboard?.drafts?.length ? (
        <ul className="hub-drafts" aria-label={H.draftGo}>
          {dash.dashboard.drafts.map((d) => (
            <li key={d.case_id}>
              <Link href={d.resume_path} className="hub-draft">
                <span className="hub-draft-text">{H.draft(d.employer, inr(d.total_due))}</span>
                <span className="hub-draft-go">
                  {H.draftGo} <ChevronRightIcon />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {acts.length ? (
        <section aria-label={H.recent} className="hub-recent">
          <h2 className="section-title">{H.recent}</h2>
          <ol className="hub-activity">
            {acts.slice(0, 5).map((a) => (
              <li key={a.key}>
                <Link href={`/case/${a.caseId}`} className="hub-act" data-tone={a.tone}>
                  <span className="hub-act-icon" aria-hidden="true">
                    {a.icon === "sent" ? <ArrowRightIcon /> : a.icon === "clock" ? <ClockIcon /> : <span className="hub-act-dot" />}
                  </span>
                  <span className="hub-act-text">
                    <span className="hub-act-who">{a.who}</span>
                    <span className="hub-act-what">{a.text}</span>
                  </span>
                  {a.when ? <span className="hub-act-when">{a.when}</span> : null}
                </Link>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

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

function Brand() {
  return (
    <Link href="/app" className="hub-brand" aria-label="Baaki">
      <LogoMark size={22} />
      <span className="hub-brand-word">Baaki</span>
    </Link>
  );
}
