"use client";

// Voice profile (/voice): plain-words consent in Telugu + Hinglish + English, record 10–20 s,
// POST with consent=true, status, delete.

import { usePressToTalk, useSettings, useT, useVoiceProfile, VOICE_MAX_MS } from "@/hooks";
import { allLangs } from "@/lib/i18n";
import { dateTime } from "@/lib/format";
import { ErrorNote, Loading, MicButton, Screen, Toggle } from "@/components/ui/primitives";

const SAMPLE: Record<string, string> = {
  te: "నా పేరు లక్ష్మి. నేను హైదరాబాద్‌లో ఇళ్ళలో పని చేస్తాను. ప్రతి రోజు ఉదయం ఏడు గంటలకు పని మొదలుపెడతాను.",
  "hi-en": "मेरा नाम रफ़ीक है। मैं Hyderabad में खाना बनाने का काम करता हूँ। रोज़ सुबह सात बजे काम शुरू करता हूँ।",
  en: "My name is Lakshmi. I work in homes in Hyderabad. I start work at seven every morning.",
};

export function VoiceScreen() {
  const settings = useSettings();
  const { t, lang } = useT();
  const vp = useVoiceProfile(settings.hydrated ? settings.workerId : null);
  const press = usePressToTalk(
    { state: vp.recorder.state, start: async () => vp.toggle(), stop: vp.recorder.stop },
    { disabled: vp.saving, holdMs: 1500 },
  );

  const recording = vp.recorder.state === "recording";
  const seconds = Math.floor(vp.recorder.elapsedMs / 1000);

  return (
    <Screen title={t("voice.title")} back="/" t={t} className="voice-screen">
      {vp.loading ? <Loading label={t("common.loading")} /> : null}

      {vp.exists && vp.profile ? (
        <section className="card voice-status" data-exists="true">
          <h2 className="card-title">{t("voice.ready")}</h2>
          {vp.profile.consent_at ? <p className="meta">{dateTime(vp.profile.consent_at, lang)}</p> : null}
          {vp.profile.duration_s ? <p className="meta">{vp.profile.duration_s.toFixed(1)} s</p> : null}
          <button type="button" className="btn btn-no" onClick={() => void vp.remove()} disabled={vp.deleting}>
            {t("voice.delete")}
          </button>
        </section>
      ) : null}

      {!vp.loading && !vp.exists ? (
        <>
          <section className="card consent" aria-labelledby="consent-title">
            <h2 id="consent-title" className="card-title">
              {t("voice.consent_title")}
            </h2>
            {allLangs("voice.consent_body").map((c) => (
              <p key={c.lang} lang={c.lang === "te" ? "te" : c.lang === "hi-en" ? "hi" : "en"} className="consent-text">
                {c.text}
              </p>
            ))}
            <Toggle
              checked={vp.consent}
              onChange={vp.setConsent}
              label={allLangs("voice.agree")
                .map((c) => c.text)
                .join(" · ")}
            />
          </section>

          {vp.justDeleted ? <p className="meta">{t("voice.deleted")}</p> : null}
          <p className="hint">{t("voice.none")}</p>

          {vp.consent ? (
            <section className="stack">
              <p className="field-label">{t("voice.say_this")}</p>
              <blockquote className="sample">{SAMPLE[lang] ?? SAMPLE.en}</blockquote>
              <MicButton
                state={vp.saving ? "busy" : vp.recorder.state}
                level={vp.recorder.level}
                disabled={vp.saving}
                handlers={press}
                label={
                  vp.saving
                    ? t("voice.saving")
                    : recording
                      ? `${seconds}/${VOICE_MAX_MS / 1000} ${t("common.seconds")} · ${vp.longEnough ? t("speak.stop") : t("voice.recording")}`
                      : t("voice.record")
                }
              />
              <progress className="voice-progress" max={1} value={vp.progress} aria-hidden="true" />
            </section>
          ) : null}
        </>
      ) : null}

      <ErrorNote message={vp.error === "consent_required" ? t("voice.consent_title") : vp.error} />
    </Screen>
  );
}
