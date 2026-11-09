"use client";

// Kaam Diary (/diary): a 5-second check-in (one tap per home, or say it), and the entries with the
// hash-chain "untouched record" badge.

import { useMemo } from "react";
import { useDashboard, useDiary, usePressToTalk, useSettings, useT } from "@/hooks";
import { dateTime, shortHash } from "@/lib/format";
import { ErrorNote, Loading, MicButton, Screen } from "@/components/ui/primitives";

export function DiaryScreen() {
  const settings = useSettings();
  const { t, lang } = useT();
  const workerId = settings.hydrated ? settings.workerId : null;
  const dash = useDashboard(workerId);
  const diary = useDiary(workerId, { lang: settings.listenLang });
  const press = usePressToTalk(diary.recorder, { disabled: diary.saving });

  const homes = useMemo(
    () => dash.cards.filter((c) => c.employer).map((c) => ({ caseId: c.case_id, employer: c.employer! })),
    [dash.cards],
  );
  const nameOf = (id: number | null) => homes.find((h) => h.employer.id === id)?.employer.name ?? "";

  return (
    <Screen title={t("diary.title")} back="/app" t={t} className="diary-screen" nav="diary">
      <section className="stack" aria-label={t("diary.checkin")}>
        <p className="hint">{t("diary.hint")}</p>
        <div className="checkin-grid">
          {homes.map((h) => (
            <button
              key={h.caseId}
              type="button"
              className="btn btn-big"
              disabled={diary.saving}
              onClick={() =>
                void diary.add({
                  text: `${t("diary.worked_at")}: ${h.employer.name}`,
                  employerId: h.employer.id,
                  caseId: h.caseId,
                  kind: "checkin",
                })
              }
            >
              {h.employer.name}
            </button>
          ))}
        </div>
        <MicButton
          size="small"
          state={diary.saving ? "busy" : diary.recorder.state}
          level={diary.recorder.level}
          elapsedMs={diary.recorder.elapsedMs}
          disabled={diary.saving}
          handlers={press}
          label={diary.recorder.state === "recording" ? t("speak.stop") : t("diary.voice")}
        />
        {diary.last ? <p className="meta">{t("diary.saved")} ✓</p> : null}
        <ErrorNote message={diary.error} />
      </section>

      {diary.chain ? (
        <p className="badge" data-valid={diary.chain.valid}>
          {diary.chain.valid ? `✓ ${t("diary.valid")}` : `✗ ${t("diary.broken")}`} · {diary.chain.count}
        </p>
      ) : null}

      {diary.loading ? <Loading label={t("common.loading")} /> : null}
      <section aria-label={t("diary.entries")}>
        <h2 className="section-title">{t("diary.entries")}</h2>
        <ol className="diary-list">
          {diary.entries.map((e) => (
            <li key={e.id} className="diary-entry" data-kind={e.kind}>
              <p className="diary-text">{e.text}</p>
              <p className="meta">
                {dateTime(e.timestamp, lang)}
                {e.employer_id ? ` · ${nameOf(e.employer_id)}` : ""}
              </p>
              <p className="meta mono" title={e.hash}>
                #{shortHash(e.hash)}
              </p>
            </li>
          ))}
        </ol>
      </section>
    </Screen>
  );
}
