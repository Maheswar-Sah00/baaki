"use client";

// Worker side of Hisaab Milao (/hisaab/[caseId]): a calm running statement with her employer. What waits for her
// comes first (so the choice is on the first screen): his "I've paid" claim ("Did the money arrive?") or a
// correction he remembers differently, read back in her language with the audio, and two big choices. Then what is
// still owed (big ink figure) and every decided line. She is always the one who decides. Confirming a payment claim
// brings the "Paisa aa gaya!" moment and its voice clip.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { errorMessage, mediaUrl } from "@/lib/api";
import { decide, getCaseHisaab, type HisaabProposal, type HisaabSummary } from "@/lib/features/hisaab";
import { inr, shortDate } from "@/lib/format";
import { uiLangOf, type UiLang } from "@/lib/i18n";
import { useAudioPlayer, useT } from "@/hooks";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { Confetti, ErrorNote, Illustration, MoneyFigure, PlayButton, Screen, SkeletonCard, StatusPill } from "@/components/ui/primitives";
import { CheckIcon, ChevronRightIcon, CrossIcon, RupeeIcon, ShieldIcon } from "@/components/ui/icons";
import { ProposalChip, whatOf } from "./ProposalChip";
import { CLAIM_WORDS, HTML_LANG, workerStrings, type WorkerStrings } from "./strings";
import s from "./hisaab.module.css";

type Player = ReturnType<typeof useAudioPlayer>;
type Celebration = { amount: string; text: string; language: string; audio: string | null };

function initialOf(name: string) {
  return Array.from(name.trim())[0]?.toUpperCase() ?? "·";
}

function Decision({
  p,
  S,
  lang,
  workerLang,
  player,
  onDone,
  onCelebrate,
}: {
  p: HisaabProposal;
  S: WorkerStrings;
  lang: UiLang;
  workerLang: UiLang;
  player: Player;
  onDone: () => void;
  onCelebrate: (c: Celebration) => void;
}) {
  const [busy, setBusy] = useState<"accept" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isClaim = p.type === "payment_claim";
  const audio = mediaUrl(p.readback.audio_url);
  const go = async (d: "accept" | "reject") => {
    setBusy(d);
    setError(null);
    try {
      const r = await decide(p.id, d);
      if (d === "accept" && r.alert) {
        onCelebrate({ amount: p.amount_display, text: r.alert.text, language: r.alert.language, audio: r.alert.audio?.url ?? null });
      }
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  // The worker's own yes / no word under an English label (Lakshmi sees "Vachindi" / "Raledu").
  const word = lang === "en" ? CLAIM_WORDS[workerLang] : CLAIM_WORDS.en;
  return (
    <article className={s.decision} data-type={p.type} data-hisaab-id={p.id} aria-label={`${p.amount_display} · ${S.saidBy(p.said_by_name)}`}>
      <header className={s.saidBy}>
        <span className="fx-avatar" data-wash="peach" aria-hidden="true">
          {initialOf(p.said_by_name)}
        </span>
        <span className={s.saidByName}>{S.saidBy(p.said_by_name)}</span>
        <span className={s.saidByWhen}>{shortDate(p.created_at, lang)}</span>
      </header>

      {isClaim ? (
        <div className={s.claimHead}>
          <h3 className={s.claimTitle}>{S.claimTitle}</h3>
          {p.status_text_worker && p.status_text_worker !== S.claimTitle ? (
            <p className={s.claimSub} lang={HTML_LANG[workerLang]}>
              {p.status_text_worker}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className={s.decTop}>
        <p className={s.decAmount}>{isClaim ? p.amount_display : p.signed_display}</p>
        <p className={s.decMeta}>
          <span className="fx-chip">{whatOf(p, lang)}</span>
        </p>
      </div>

      <p className={s.readback} lang={HTML_LANG[uiLangOf(p.readback.language)]}>
        {p.readback.text}
      </p>
      {audio ? (
        <div className={s.listenRow}>
          <PlayButton
            state={player.state}
            active={player.isCurrent(audio)}
            progress={player.progress}
            onClick={() => void player.toggle(audio)}
            label={S.listen}
          />
        </div>
      ) : null}

      {!isClaim && p.transcript.trim() ? (
        <figure className={s.quote}>
          <figcaption>{S.theirWords}</figcaption>
          <blockquote lang={HTML_LANG[uiLangOf(p.language)]}>&ldquo;{p.transcript}&rdquo;</blockquote>
        </figure>
      ) : null}

      {p.exceeds_balance && !isClaim ? (
        <p className={s.warn} role="note">
          {S.exceeds}
        </p>
      ) : (
        <p className={s.ifYes}>
          <RupeeIcon /> {isClaim ? S.claimIfYes(p.amount_display) : S.ifYes(p.amount_display)}
        </p>
      )}

      <div className={s.actions} data-stack={isClaim}>
        <button
          type="button"
          className={s.choice}
          data-kind="yes"
          disabled={busy !== null || (p.exceeds_balance && !isClaim)}
          onClick={() => void go("accept")}
        >
          <CheckIcon />
          <span className={s.choiceText}>
            {isClaim ? S.claimYes : S.yes}
            {isClaim && word.yes ? <small>{word.yes}</small> : null}
          </span>
        </button>
        <button type="button" className={s.choice} data-kind="no" disabled={busy !== null} onClick={() => void go("reject")}>
          <CrossIcon />
          <span className={s.choiceText}>
            {isClaim ? S.claimNo : S.no}
            {isClaim && word.no ? <small>{word.no}</small> : null}
          </span>
        </button>
      </div>
      <ErrorNote message={error} />
    </article>
  );
}

function Paisa({ c, S, player, onClose }: { c: Celebration; S: WorkerStrings; player: Player; onClose: () => void }) {
  return (
    <div className={s.celebrate} role="dialog" aria-modal="true" aria-labelledby="hisaab-paisa">
      <div className={s.celebrateCard}>
        <div className={s.celebrateArt} data-wash="sage">
          <Confetti pieces={16} />
          <Illustration name="celebrate" className={s.celebrateIll} />
        </div>
        <div className={s.celebrateBody}>
          <p id="hisaab-paisa" className={s.celebrateTitle}>
            {S.paisa}
          </p>
          <p className={s.celebrateAmount}>{c.amount}</p>
          <p className={s.celebrateText} lang={HTML_LANG[uiLangOf(c.language)]}>
            {c.text}
          </p>
          {c.audio ? (
            <PlayButton
              state={player.state}
              active={player.isCurrent(c.audio)}
              progress={player.progress}
              onClick={() => void player.toggle(c.audio)}
              label={S.listen}
            />
          ) : null}
          <button type="button" className={s.celebrateOk} onClick={onClose} autoFocus>
            {S.ok}
          </button>
        </div>
      </div>
    </div>
  );
}

export function HisaabWorker({ caseId }: { caseId: string }) {
  const { t, lang } = useT();
  const S = workerStrings(lang);
  const player = useAudioPlayer();
  const [data, setData] = useState<HisaabSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [celebration, setCelebration] = useState<Celebration | null>(null);

  const load = useCallback(() => {
    getCaseHisaab(caseId)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [caseId]);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000); // a new proposal or claim from the employer lands here
    return () => window.clearInterval(id);
  }, [load]);

  const celebrate = (c: Celebration) => {
    setCelebration(c);
    if (c.audio) void player.play(c.audio); // she just tapped Yes: autoplay is allowed; if not, the button stays
  };

  const back = `/case/${encodeURIComponent(caseId)}`;
  if (!data) {
    return (
      <Screen title={S.title} back={back} t={t} className={`fx ${s.screen}`}>
        {error ? (
          <ErrorNote message={error} onRetry={load} retryLabel={t("common.retry")} />
        ) : (
          <div className="stack" role="status" aria-label={t("common.loading")}>
            <SkeletonCard />
            <SkeletonCard />
          </div>
        )}
      </Screen>
    );
  }

  const employer = data.employer.name;
  const workerLang = uiLangOf(data.worker.language);
  const pending = data.proposals.filter((p) => p.status === "proposed");
  const decided = data.proposals.filter((p) => p.status !== "proposed");
  const agreed = decided.some((p) => p.status === "accepted");

  return (
    <Screen title={S.title} back={back} t={t} className={`fx ${s.screen}`}>
      <header className={s.head} lang={HTML_LANG[lang]}>
        <p className="fx-eyebrow">{S.eyebrow(employer)}</p>
        <h1 className={`fx-h ${s.h}`}>
          {S.lead} <em>{S.accent}</em>
        </h1>
        {pending.length ? null : <p className="fx-sub">{S.sub(employer)}</p>}
      </header>

      {error ? <ErrorNote message={error} onRetry={load} retryLabel={t("common.retry")} /> : null}

      {pending.length ? (
        <section className={s.section} aria-label={S.waiting} lang={HTML_LANG[lang]}>
          {pending.length > 1 ? (
            <div className={s.sectionHead}>
              <h2 className="section-title">{S.waiting}</h2>
              <span className={s.count}>{pending.length}</span>
            </div>
          ) : null}
          {pending.map((p) => (
            <Decision key={p.id} p={p} S={S} lang={lang} workerLang={workerLang} player={player} onDone={load} onCelebrate={celebrate} />
          ))}
        </section>
      ) : (
        <section className={s.empty} lang={HTML_LANG[lang]}>
          {agreed ? (
            <Illustration name="handshake" className={s.emptyArt} />
          ) : (
            <AssetSlot name="can-do-promise-keeper" alt="" ratio="1353/986" tone="butter" fit="contain" className={s.emptyArt} rounded="20px" />
          )}
          <p className="fx-h2">{S.none}</p>
          <p className="fx-muted">{S.noneHint(employer)}</p>
        </section>
      )}

      <section className={s.statement} aria-label={S.stillOwed} lang={HTML_LANG[lang]}>
        <div className={s.stTop}>
          <span className="fx-avatar" data-wash="peach" aria-hidden="true">
            {initialOf(employer)}
          </span>
          <div className={s.stWho}>
            <p className={s.stName}>{employer}</p>
            <p className="fx-muted">{S.stillOwed}</p>
          </div>
          {data.pending > 0 ? (
            <StatusPill tone="warn">
              {data.pending} · {S.waiting}
            </StatusPill>
          ) : null}
        </div>
        <p className={s.stFigure} aria-live="polite">
          <MoneyFigure value={data.balance} size="xl" />
        </p>
        <dl className={s.stats}>
          <div>
            <dt>{S.total}</dt>
            <dd>{inr(data.total_due)}</dd>
          </div>
          <div data-tone={data.amount_paid > 0 ? "paid" : undefined}>
            <dt>{S.paid}</dt>
            <dd>{inr(data.amount_paid)}</dd>
          </div>
          <div data-tone={data.disputed_total > 0 ? "disputed" : undefined}>
            <dt>{S.disputed}</dt>
            <dd>{inr(data.disputed_total)}</dd>
          </div>
        </dl>
        <p className={s.notice}>
          <ShieldIcon /> {S.notice}
        </p>
      </section>

      {decided.length > 0 ? (
        <section className={s.section} aria-label={S.decided} lang={HTML_LANG[lang]}>
          <h2 className="section-title" style={{ margin: 0 }}>
            {S.decided}
          </h2>
          <div className={s.ledger}>
            <ul className={s.ledgerList}>
              {decided.map((p) => (
                <li key={p.id}>
                  <ProposalChip p={p} side="worker" lang={lang} />
                </li>
              ))}
            </ul>
            <p className={s.sum}>
              <span>{S.balance}</span>
              <span>{data.balance_display}</span>
            </p>
          </div>
        </section>
      ) : null}

      {celebration ? (
        <Paisa
          c={celebration}
          S={S}
          player={player}
          onClose={() => {
            player.stop();
            setCelebration(null);
          }}
        />
      ) : null}
    </Screen>
  );
}

/**
 * Mount on the case screen: a compact card for what waits in the running account, linking to /hisaab/[caseId].
 * Renders nothing until a proposal or claim exists. A waiting "I've paid" claim leads ("Sharma ji says he paid
 * ₹13,000. Did it arrive?").
 */
export function HisaabCaseCard({ caseId }: { caseId: number | string }) {
  const { lang } = useT();
  const S = workerStrings(lang);
  const [data, setData] = useState<HisaabSummary | null>(null);
  useEffect(() => {
    let alive = true;
    const pull = () =>
      getCaseHisaab(caseId)
        .then((d) => alive && setData(d))
        .catch(() => alive && setData(null));
    void pull();
    const id = window.setInterval(pull, 10000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [caseId]);
  if (!data || data.proposals.length === 0) return null;
  const claim = data.proposals.find((p) => p.status === "proposed" && p.type === "payment_claim");
  const waiting = data.proposals.filter((p) => p.status === "proposed");
  const latest = claim ?? waiting[0] ?? data.proposals[0];
  const title = claim
    ? S.claimCard(data.employer.name, claim.amount_display)
    : waiting.length
      ? S.cardTitle(data.employer.name, waiting.length)
      : S.cardIdle;
  return (
    <Link
      className={s.caseCard}
      data-urgent={waiting.length > 0}
      href={`/hisaab/${encodeURIComponent(String(caseId))}`}
      lang={HTML_LANG[lang]}
    >
      <span className={s.caseCardTop}>
        <span className={s.caseCardIcon} aria-hidden="true">
          {claim ? <RupeeIcon /> : waiting.length ? <ShieldIcon /> : <CheckIcon />}
        </span>
        <span className={s.caseCardTitle}>{title}</span>
        <ChevronRightIcon />
      </span>
      <ProposalChip p={latest} side="worker" lang={lang} />
      {waiting.length ? <span className={s.caseCardCta}>{S.checkNow}</span> : null}
    </Link>
  );
}

