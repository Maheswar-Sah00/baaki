"use client";

// /inbox/[caseId]: the employer's WhatsApp replies for one case, saved as hashed proof, with Promise Keeper.
// Hero: a "Promise passed: remind?" card when a promised date has gone by unpaid; otherwise the add button.
// `asOf` (from ?as_of=YYYY-MM-DD) shifts "today" for the demo ("a week later").

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, GradientButton, Screen, SkeletonCard } from "@/components/ui/primitives";
import { AssetSlot } from "@/components/ui/AssetSlot";
import { LockIcon } from "@/components/ui/icons";
import { useAudioPlayer, useT } from "@/hooks";
import { getInbox, type InboxAdded, type InboxList, type InboxPromise } from "@/lib/features/inbox";
import { getCaseHisaab } from "@/lib/features/hisaab";
import { AddReplySheet } from "./AddReplySheet";
import { EvidenceCard } from "./EvidenceCard";
import { ReminderCard } from "./ReminderCard";
import { clearSharedFile, readSharedFile } from "./sharedFile";
import { inboxStrings } from "./strings";
import css from "./inbox.module.css";

export function InboxScreen({ caseId, asOf, shared }: { caseId: number; asOf?: string | null; shared?: boolean }) {
  const { t, lang } = useT();
  const S = inboxStrings(lang);
  const player = useAudioPlayer();
  const [data, setData] = useState<InboxList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sheet, setSheet] = useState(false);
  const [fresh, setFresh] = useState<{ id: number; duplicate: boolean } | null>(null);
  const [sharedIn, setSharedIn] = useState<{ file: File | null; text: string | null } | null>(null);

  // Arrived from the PWA share target (/inbox/share -> /inbox/{id}?shared=1): open the sheet with that note.
  useEffect(() => {
    if (!shared) return;
    let live = true;
    void readSharedFile().then(async (f) => {
      if (!live || !f) return;
      const text = f.type === "text/plain" ? await f.text() : null;
      setSharedIn({ file: text ? null : f, text });
      setSheet(true);
    });
    return () => {
      live = false;
    };
  }, [shared]);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const d = await getInbox(caseId, asOf, signal);
        setData(d);
        setError(null);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(S.error);
      } finally {
        setLoading(false);
      }
    },
    [caseId, asOf, S.error],
  );

  useEffect(() => {
    const ac = new AbortController();
    // load() only sets state after its fetch resolves, not synchronously in this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(ac.signal);
    return () => ac.abort();
  }, [load]);

  const onAdded = useCallback(
    (r: InboxAdded) => {
      setFresh({ id: r.id, duplicate: r.duplicate });
      if (shared) void clearSharedFile();
      if (r.audio_url) void player.play(r.audio_url);
      void load();
      if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [load, player, shared],
  );

  const onPromise = useCallback((p: InboxPromise) => {
    setData((d) =>
      d
        ? {
            ...d,
            cards: d.cards.map((c) => ({
              ...c,
              promises: c.promises.map((x) => (x.id === p.id ? p : x)),
              promise: c.promise?.id === p.id ? p : c.promise,
            })),
            promises: d.promises.map((x) => (x.id === p.id ? p : x)),
            passed: d.passed.filter((x) => x.id !== p.id || p.status === "passed"),
          }
        : d,
    );
  }, []);

  // A card mentions money he says he paid: link to Hisaab only while a claim waits for her answer there.
  const mentionsPaid = !!data?.cards.some((c) => c.past_payments?.length);
  const [claimPending, setClaimPending] = useState(false);
  useEffect(() => {
    if (!mentionsPaid) return;
    const ac = new AbortController();
    getCaseHisaab(caseId, ac.signal)
      .then((h) => setClaimPending((h.pending_claims ?? 0) > 0))
      .catch(() => undefined);
    return () => ac.abort();
  }, [caseId, mentionsPaid]);
  const claimHref = mentionsPaid && claimPending ? `/hisaab/${caseId}` : null;

  const employer = data?.case.employer.name ?? "";
  const passed = data?.passed ?? [];

  return (
    <Screen title={S.title} back={`/case/${caseId}`} t={t} className="fx">
      {loading && !data ? (
        <div role="status" aria-label={t("common.loading")} className="stack">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}
      {!data && !loading ? <ErrorNote message={error} onRetry={() => void load()} retryLabel={S.retry} /> : null}

      {data ? (
        <>
          {passed.map((p, i) => (
            <ReminderCard key={p.id} promise={p} S={S} lang={lang} asOf={asOf} glow={i === 0} onChanged={onPromise} />
          ))}

          <p className={css.intro}>{S.intro(employer)}</p>
          {passed.length ? (
            <button type="button" className="fx-pill-btn" style={{ minHeight: 54 }} onClick={() => setSheet(true)}>
              {S.add}
            </button>
          ) : (
            <GradientButton onClick={() => setSheet(true)}>{S.add}</GradientButton>
          )}

          {data.cards.length === 0 ? (
            <div className="stack slot-empty" style={{ justifyItems: "center", textAlign: "center" }}>
              <AssetSlot name="inbox-empty-whatsapp" alt="" ratio="16/10" tone="sage" rounded="var(--card-r)" fit="contain" />
              <p className="fx-h2">{S.empty}</p>
              <p className="fx-muted">{S.emptyHint}</p>
            </div>
          ) : (
            <ul className={css.list}>
              {data.cards.map((c) => (
                <li key={c.id}>
                  <EvidenceCard
                    card={c}
                    S={S}
                    lang={lang}
                    asOf={asOf}
                    fresh={fresh?.id === c.id}
                    duplicate={fresh?.id === c.id && fresh.duplicate}
                    player={player}
                    onPromise={onPromise}
                    claimHref={claimHref}
                  />
                </li>
              ))}
            </ul>
          )}

          {data.cards.length ? (
            <p className={css.chain} data-ok={data.chain.valid && data.chain.cards_linked}>
              <LockIcon /> {data.chain.valid && data.chain.cards_linked ? S.chainOk(data.chain.count) : S.chainBroken}
            </p>
          ) : null}
          <p className="footnote">{t("common.not_legal_advice")}</p>
        </>
      ) : null}

      <AddReplySheet
        key={sharedIn ? "shared" : "plain"}
        open={sheet}
        onClose={() => setSheet(false)}
        caseId={caseId}
        S={S}
        onAdded={onAdded}
        initialFile={sharedIn?.file ?? null}
        initialText={sharedIn?.text ?? null}
      />
    </Screen>
  );
}
