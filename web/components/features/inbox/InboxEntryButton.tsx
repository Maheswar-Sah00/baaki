"use client";

// Mount point for CaseScreen: "WhatsApp reply aaya?" -> /inbox/{caseId}. Shows a pill when a promise has passed.

import { useEffect, useState } from "react";
import { Card, StatusPill } from "@/components/ui/primitives";
import { ArrowRightIcon, WaveIcon } from "@/components/ui/icons";
import { useT } from "@/hooks";
import { getInbox } from "@/lib/features/inbox";
import { inboxStrings } from "./strings";
import css from "./inbox.module.css";

export function InboxEntryButton({ caseId }: { caseId: number }) {
  const { lang } = useT();
  const S = inboxStrings(lang);
  const [passed, setPassed] = useState(0);

  useEffect(() => {
    const ac = new AbortController();
    getInbox(caseId, null, ac.signal)
      .then((d) => setPassed(d.passed.length))
      .catch(() => undefined);
    return () => ac.abort();
  }, [caseId]);

  return (
    <Card href={`/inbox/${caseId}`} className={css.entry} aria-label={S.entry}>
      <span className={css.entryIcon} aria-hidden="true">
        <WaveIcon />
      </span>
      <span className={css.entryText}>
        <span className={css.entryTitle}>{S.entry}</span>
        <span className={css.entryHint}>{S.entryHint}</span>
      </span>
      {passed ? <StatusPill tone="warn">{S.status.passed}</StatusPill> : <ArrowRightIcon />}
    </Card>
  );
}
