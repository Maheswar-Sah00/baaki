"use client";

// Home-screen card for Haq Raise: "₹18,000 more a year is possible", linking to the best home's raise page.
// Mount (main session): <RaiseCard workerId={workerId} />
// Renders nothing while loading, on error, or when no home pays below the estimate and nothing was won.

import { useEffect, useState } from "react";
import { Card, StatusPill } from "@/components/ui/primitives";
import { ArrowRightIcon } from "@/components/ui/icons";
import { useT } from "@/hooks";
import { raiseApi, raiseLangOf, rupees, type RaiseSummary } from "@/lib/features/raise";
import { CARD } from "./strings";
import css from "./raise.module.css";

export function RaiseCard({ workerId }: { workerId: number | null | undefined }) {
  const { lang } = useT();
  const rl = raiseLangOf(lang);
  const C = CARD[rl];
  const [s, setS] = useState<RaiseSummary | null>(null);

  useEffect(() => {
    if (!workerId) return;
    const ac = new AbortController();
    raiseApi
      .summary(workerId, ac.signal)
      .then(setS)
      .catch(() => undefined);
    return () => ac.abort();
  }, [workerId]);

  if (!workerId || !s) return null;
  const possible = s.total_yearly_gain_possible;
  const won = s.total_yearly_gain_won;
  if (possible <= 0 && won <= 0) {
    // Hours never said: the estimate can't be made (never guessed as 8 h), so ask her to tell Baaki.
    // (`needs_hours` is a summary status the shared HomeStatus type does not list yet.)
    const noHours = s.per_home.find((h) => String(h.status) === "needs_hours");
    if (!noHours) return null;
    return (
      <Card href="/speak" className={css.card} aria-label={C.needsHours}>
        <div>
          <p className={css.cardValue}>{C.needsHours}</p>
          {noHours.employer ? <p className={css.cardSub}>{C.needsHoursSub(noHours.employer)}</p> : null}
        </div>
        <span className={css.cardIcon} aria-hidden="true">
          <ArrowRightIcon />
        </span>
      </Card>
    );
  }

  const best = s.per_home.find((h) => h.case_id === s.best_case_id);
  const href = s.best_url ?? s.per_home.find((h) => h.status === "accepted" || h.status === "stepped")?.url ?? "/app";
  return (
    <Card href={href} className={css.card} aria-label={possible > 0 ? C.possible(rupees(possible)) : C.won(rupees(won))}>
      <div>
        {possible > 0 ? (
          <>
            <p className={css.cardValue}>{C.possible(rupees(possible))}</p>
            {best ? <p className={css.cardSub}>{C.sub(best.employer)}</p> : null}
          </>
        ) : null}
        {won > 0 ? (
          <p className={possible > 0 ? css.cardSub : css.cardValue}>
            <StatusPill tone="success">{C.won(rupees(won))}</StatusPill>
          </p>
        ) : null}
      </div>
      <span className={css.cardIcon} aria-hidden="true">
        <ArrowRightIcon />
      </span>
    </Card>
  );
}
