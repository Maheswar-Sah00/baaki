"use client";

// "Sharma ji's phone": the cached voice note, what is owed with one big "Mark as paid", the itemised dues, the
// message text, UPI and voice reply switched off. Laid out like a payment screen: the action sits right under the
// total so it is on the first screen.

import type { SandboxView } from "@/lib/features/sandbox";
import { useAudioPlayer } from "@/hooks";
import { PlayButton } from "@/components/ui/primitives";
import { BotIcon, CheckIcon, LockIcon } from "@/components/ui/icons";
import { Banner } from "./Banner";
import css from "./sandbox.module.css";

type Props = {
  view: SandboxView;
  paying: boolean;
  payError: string | null;
  onPlayed: () => void;
  onPay: () => void;
};

export function EmployerPhone({ view, paying, payError, onPlayed, onPay }: Props) {
  const player = useAudioPlayer();
  const included = view.items.filter((i) => i.included_in_total);
  const shown = view.items.filter((i) => !i.included_in_total);
  const url = view.voice_note.available ? view.voice_note.audio_url : null;
  return (
    <div className={css.app} aria-label="Sharma ji's phone">
      <div className={css.appHead}>
        <span className={css.appTitle}>{view.worker.name} · Baaki</span>
        <Banner compact />
      </div>

      <section className={css.voice} data-wash="lilac">
        <p className={css.voiceTitle}>Voice note from {view.worker.name}</p>
        {url ? (
          <PlayButton
            state={player.state}
            active={player.isCurrent(url)}
            progress={player.progress}
            onClick={() => {
              onPlayed();
              void player.toggle(url);
            }}
            label="Play"
          />
        ) : null}
        <p className={css.voiceNote}>
          <BotIcon /> {url ? view.voice_note.label : `${view.voice_note.label}. ${view.voice_note.reason ?? ""}`}
        </p>
      </section>

      <section className={css.due}>
        <p className={css.dueLabel}>{view.paid ? "Still due" : "Total due"}</p>
        <p className={css.dueValue} data-paid={view.paid}>
          {view.balance_display}
        </p>
        {view.paid ? (
          <p className={css.paidNote} role="status">
            <CheckIcon /> Marked as paid.{view.badge ? ` ${view.badge.text_en}` : ""}
          </p>
        ) : (
          <button type="button" className={css.payBtn} onClick={onPay} disabled={paying}>
            {paying ? "Marking as paid…" : "Mark as paid"}
          </button>
        )}
        {payError ? (
          <p role="alert" className={css.error}>
            {payError}
          </p>
        ) : null}
      </section>

      <section className={css.owed}>
        <p className={css.sectionLabel}>What is owed</p>
        <ul className={css.lines}>
          {included.map((i) => (
            <li key={i.id}>
              <span>
                {i.label_en}
                {i.due_date ? <small> · due {i.due_date}</small> : null}
              </span>
              <b>{i.amount_display}</b>
            </li>
          ))}
        </ul>
        {shown.map((i) => (
          <p key={i.id} className={css.small}>
            {i.label_en}: {i.amount_display} {i.is_estimate ? "(estimate, not added to the total)" : ""}
          </p>
        ))}
      </section>

      {view.message?.text ? (
        <section className={css.message}>
          <p className={css.sectionLabel}>Her message</p>
          <p className={css.bubble} lang="hi">
            {view.message.text}
          </p>
        </section>
      ) : null}
      <p className={css.small}>{view.ai_notice}</p>
      <p className={css.off}>
        <LockIcon /> {view.upi.label}
      </p>
      <p className={css.off}>
        <LockIcon /> {view.reply.label}
      </p>
    </div>
  );
}
