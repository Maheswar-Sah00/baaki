"use client";

// One forwarded WhatsApp reply, saved as proof: the one-line summary ("Sharma ji said on 9 Nov: will pay
// ₹12,000 by 14 Nov"), the employer's own words as the chat bubble they came in (with their voice note), the
// promise chip(s), the translation with its Timbre read-out, and the hash that links it into her diary chain.

import Link from "next/link";
import { PlayButton } from "@/components/ui/primitives";
import { ArrowRightIcon, LockIcon } from "@/components/ui/icons";
import { shortDate } from "@/lib/format";
import type { UiLang } from "@/lib/i18n";
import type { InboxCard, InboxPromise } from "@/lib/features/inbox";
import type { useAudioPlayer } from "@/hooks";
import { PromiseChip } from "./PromiseChip";
import type { InboxStrings } from "./strings";
import css from "./inbox.module.css";

const HTML_LANG: Record<string, string> = { "te-IN": "te", "hi-en": "hi", en: "en" };

export function EvidenceCard({
  card,
  S,
  lang,
  asOf,
  fresh,
  duplicate,
  player,
  onPromise,
  claimHref,
}: {
  card: InboxCard;
  S: InboxStrings;
  lang: UiLang;
  asOf?: string | null;
  fresh?: boolean;
  duplicate?: boolean;
  player: ReturnType<typeof useAudioPlayer>;
  onPromise: (p: InboxPromise) => void;
  /** /hisaab/{caseId}, only while an "I've paid" claim waits for her answer there. */
  claimHref?: string | null;
}) {
  const play = (url: string | null, label: string) =>
    url ? (
      <PlayButton
        state={player.state}
        active={player.isCurrent(url)}
        progress={player.progress}
        onClick={() => void player.toggle(url)}
        label={label}
      />
    ) : null;

  return (
    <article className={`${css.card} ${fresh ? css.fresh : css.rise}`} data-fresh={fresh ? "true" : undefined}>
      <div className={css.cardHead}>
        <p className={css.summary} lang={HTML_LANG[card.summary.language] ?? undefined}>
          {card.summary.text}
        </p>
        <span className={css.proof}>
          <LockIcon /> {duplicate ? S.duplicate : S.proofSaved}
        </span>
      </div>

      <div className={css.chat}>
        <p className={css.chatWho}>{S.theySaid}</p>
        <div className={css.bubble}>
          <p className={css.bubbleText} lang={HTML_LANG[card.language_code] ?? undefined}>
            {card.transcript}
          </p>
          <span className={css.bubbleTime}>{shortDate(card.said_on, lang)}</span>
        </div>
        {card.original_audio_url ? play(card.original_audio_url, S.original) : null}
      </div>

      {card.promises.length ? (
        card.promises.map((p) => <PromiseChip key={p.id} promise={p} S={S} lang={lang} asOf={asOf} onChanged={onPromise} />)
      ) : (
        <p className={css.note}>{S.noPromise}</p>
      )}

      {/* payments he says he already made: read-only, in her language; nothing is recorded from this */}
      {card.past_payments?.length ? (
        <div className={css.past}>
          <p className={css.blockLabel}>{S.pastTitle}</p>
          <ul className={css.pastList}>
            {card.past_payments.map((x, i) => (
              <li key={`${x.paid_on ?? ""}-${x.amount ?? ""}-${i}`} lang={HTML_LANG[x.line_lang] ?? undefined}>
                {x.line}
              </li>
            ))}
          </ul>
          <div className={css.pastFoot}>
            <p className={css.pastNote}>{S.pastNote}</p>
            {claimHref ? (
              <Link href={claimHref} className={css.pastLink}>
                {S.pastCheck} <ArrowRightIcon />
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className={css.block}>
        <p className={css.blockLabel}>{S.inYourLang}</p>
        <p className={css.translation} lang={HTML_LANG[card.translation_lang] ?? undefined}>
          {card.translation}
        </p>
        {card.audio_url ? play(card.audio_url, S.listen) : null}
      </div>

      <div className={css.foot}>
        <p className={css.when}>{shortDate(card.said_on, lang)}</p>
        <p className={css.hash} title={card.card.hash}>
          <LockIcon /> {S.hash(card.card.hash.slice(0, 12))}
        </p>
      </div>
    </article>
  );
}
