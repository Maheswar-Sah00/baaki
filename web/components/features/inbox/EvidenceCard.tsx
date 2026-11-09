"use client";

// One forwarded WhatsApp reply, saved as proof: the one-line summary ("Sharma ji said on 9 Nov: will pay
// ₹12,000 by 14 Nov"), the promise chip(s), the translation with its Timbre read-out, the employer's own words
// and voice note, and the hash that links it into her diary chain.

import { Card, PlayButton, StatusPill } from "@/components/ui/primitives";
import { LockIcon } from "@/components/ui/icons";
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
}: {
  card: InboxCard;
  S: InboxStrings;
  lang: UiLang;
  asOf?: string | null;
  fresh?: boolean;
  duplicate?: boolean;
  player: ReturnType<typeof useAudioPlayer>;
  onPromise: (p: InboxPromise) => void;
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
    <Card as="article" tone={fresh ? "soft" : "default"} className={fresh ? css.fresh : css.rise}>
      <div className="stack">
        <div className={css.cardHead}>
          <p className={css.summary} lang={HTML_LANG[card.summary.language] ?? undefined}>
            {card.summary.text}
          </p>
          <StatusPill tone="success" dot={false}>
            <LockIcon /> {duplicate ? S.duplicate : S.proofSaved}
          </StatusPill>
        </div>

        {card.promises.length ? (
          card.promises.map((p) => <PromiseChip key={p.id} promise={p} S={S} lang={lang} asOf={asOf} onChanged={onPromise} />)
        ) : (
          <p className={css.note}>{S.noPromise}</p>
        )}

        <div className={css.block}>
          <p className={css.blockLabel}>{S.inYourLang}</p>
          <p className={css.translation} lang={HTML_LANG[card.translation_lang] ?? undefined}>
            {card.translation}
          </p>
          {card.audio_url ? play(card.audio_url, S.listen) : null}
        </div>

        <details className={css.block}>
          <summary className={css.blockLabel}>{S.theySaid}</summary>
          <p className={css.quote} lang={HTML_LANG[card.language_code] ?? undefined}>
            {card.transcript}
          </p>
          {card.original_audio_url ? play(card.original_audio_url, S.original) : null}
        </details>

        <p className={css.when}>{shortDate(card.said_on, lang)}</p>
        <p className={css.hash} title={card.card.hash}>
          <LockIcon /> {S.hash(card.card.hash.slice(0, 12))}
        </p>
      </div>
    </Card>
  );
}
