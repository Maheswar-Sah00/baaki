"use client";

// /inbox/share: where the PWA share target lands (add-on). The shared note waits in Cache Storage; she picks the
// home, then /inbox/{caseId}?shared=1 opens the add sheet with it.

import { useEffect, useState } from "react";
import { Card, ErrorNote, Screen, SkeletonCard } from "@/components/ui/primitives";
import { ArrowRightIcon } from "@/components/ui/icons";
import { useSettings, useT } from "@/hooks";
import { getDashboard } from "@/lib/api";
import { inr } from "@/lib/format";
import type { DashboardCard } from "@/lib/types";
import { readSharedFile } from "./sharedFile";
import { inboxStrings } from "./strings";
import css from "./inbox.module.css";

export function SharePicker() {
  const { t, lang } = useT();
  const S = inboxStrings(lang);
  const { workerId, hydrated } = useSettings();
  const [cards, setCards] = useState<DashboardCard[] | null>(null);
  const [file, setFile] = useState<File | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void readSharedFile().then(setFile);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const ac = new AbortController();
    getDashboard(workerId, ac.signal)
      .then((d) => setCards(d.cards))
      .catch(() => setErr(S.error));
    return () => ac.abort();
  }, [hydrated, workerId, S.error]);

  return (
    <Screen title={S.title} back="/app" t={t} className="fx">
      <h2 className="section-title">{S.pickTitle}</h2>
      {file === null ? <p className="hint">{S.pickNone}</p> : <p className="hint">{file ? S.chosen(file.name) : S.pickHint}</p>}
      <ErrorNote message={err} />
      {!cards && !err ? <SkeletonCard /> : null}
      <ul className={css.list}>
        {(cards ?? []).map((c) => (
          <li key={c.case_id}>
            <Card href={`/inbox/${c.case_id}?shared=1`} className={css.entry}>
              <span className="fx-avatar" aria-hidden="true">
                {(c.employer?.name ?? "#").trim().charAt(0).toUpperCase()}
              </span>
              <span className={css.entryText}>
                <span className={css.entryTitle}>{c.employer?.name ?? `#${c.case_id}`}</span>
                <span className={css.entryHint}>{inr(c.balance)}</span>
              </span>
              <ArrowRightIcon />
            </Card>
          </li>
        ))}
      </ul>
    </Screen>
  );
}
