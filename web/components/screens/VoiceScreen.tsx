"use client";

// Voice profile (/voice): plain-words consent in Telugu + Hinglish + English, record 10–20 s,
// POST with consent=true, status, delete.

import { usePressToTalk, useSettings, useT, useVoiceProfile, VOICE_MAX_MS } from "@/hooks";
import { allLangs, type UiLang } from "@/lib/i18n";
import { dateTime } from "@/lib/format";
import Link from "next/link";
import { ErrorNote, Loading, MicButton, Screen, Toggle } from "@/components/ui/primitives";
import { ArrowRightIcon, CheckIcon, LockIcon, MicIcon } from "@/components/ui/icons";

const SAMPLE: Record<string, string> = {
  te: "నా పేరు లక్ష్మి. నేను హైదరాబాద్‌లో ఇళ్ళలో పని చేస్తాను. ప్రతి రోజు ఉదయం ఏడు గంటలకు పని మొదలుపెడతాను.",
  "hi-en": "मेरा नाम रफ़ीक है। मैं Hyderabad में खाना बनाने का काम करता हूँ। रोज़ सुबह सात बजे काम शुरू करता हूँ।",
  en: "My name is Lakshmi. I work in homes in Hyderabad. I start work at seven every morning.",
};

// Screen-only headline (the shared i18n keys carry the consent text itself).
const VX: Record<UiLang, { h1: string; em: string; sub: string; say: string; sayHint: string }> = {
  en: {
    h1: "Notes to employers,",
    em: "in your voice",
    sub: "Optional. Only with your yes. Delete it any time.",
    say: "Set up my voice by saying the consent",
    sayHint: "Say one sentence aloud. Baaki checks it word by word.",
  },
  te: {
    h1: "యజమానికి సందేశాలు,",
    em: "మీ గొంతులో",
    sub: "మీ ఇష్టం. మీరు ఒప్పుకుంటేనే. ఎప్పుడైనా తొలగించవచ్చు.",
    say: "ఒప్పుదల వాక్యం చెప్పి నా గొంతు సెట్ చేయండి",
    sayHint: "ఒక వాక్యం గట్టిగా చెప్పండి. బాకీ ప్రతి పదం సరిచూస్తుంది.",
  },
  "hi-en": {
    h1: "Employer ko message,",
    em: "aapki awaaz mein",
    sub: "Aapki marzi. Sirf aapki haan se. Kabhi bhi delete karein.",
    say: "Consent bolkar meri awaaz set karein",
    sayHint: "Ek vaakya bol kar sunaiye. Baaki har shabd check karega.",
  },
};
const LANG_TAG: Record<string, string> = { te: "TE", "hi-en": "HI", en: "EN" };
const BARS = [0.4, 0.7, 1, 0.6, 0.85, 0.5, 0.95, 0.65, 0.8, 0.45, 0.9, 0.55, 0.75, 0.4, 0.7, 1, 0.6, 0.5];

function Bars() {
  return (
    <span className="vx-wave" aria-hidden="true">
      {BARS.map((h, i) => (
        <i key={i} style={{ height: `${h * 100}%`, animationDelay: `${(i % 6) * 140}ms` }} />
      ))}
    </span>
  );
}

export function VoiceScreen() {
  const settings = useSettings();
  const { t, lang } = useT();
  const L = VX[lang] ?? VX.en;
  const vp = useVoiceProfile(settings.hydrated ? settings.workerId : null);
  const press = usePressToTalk(
    { state: vp.recorder.state, start: async () => vp.toggle(), stop: vp.recorder.stop },
    { disabled: vp.saving, holdMs: 1500 },
  );

  const recording = vp.recorder.state === "recording";
  const seconds = Math.floor(vp.recorder.elapsedMs / 1000);

  return (
    <Screen title={t("voice.title")} back="/app" t={t} className="fx voice-fx" nav="voice">
      {vp.loading ? <Loading label={t("common.loading")} /> : null}

      {vp.exists && vp.profile ? (
        <section className="fx-panel vx-hero" data-wash="sage" data-exists="true">
          <Bars />
          <h2 className="fx-h2 vx-ready-title fx-wash-ink">
            <span className="vx-check" aria-hidden="true">
              <CheckIcon />
            </span>
            {t("voice.ready")}
          </h2>
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {vp.profile.consent_at ? <span className="fx-chip" style={{ background: "var(--surface)" }}><LockIcon /> {dateTime(vp.profile.consent_at, lang)}</span> : null}
            {vp.profile.duration_s ? <span className="fx-chip" style={{ background: "var(--surface)" }}>{vp.profile.duration_s.toFixed(1)} s</span> : null}
          </div>
          <button type="button" className="fx-pill-btn" onClick={() => void vp.remove()} disabled={vp.deleting} style={{ justifySelf: "start" }}>
            {t("voice.delete")}
          </button>
        </section>
      ) : null}

      {!vp.loading && !vp.exists ? (
        <>
          <section className="fx-panel vx-hero" data-wash="lilac">
            <Bars />
            <h2 className="fx-h fx-wash-ink" lang={lang === "te" ? "te" : undefined}>
              {L.h1} <em>{L.em}</em>
            </h2>
            <p className="fx-sub fx-wash-ink">{L.sub}</p>
          </section>

          {/* the spoken-consent flow (her own words are the voice sample) */}
          <Link href="/voice/consent" className="card legal-pack vx-say">
            <span className="legal-pack-icon" aria-hidden="true">
              <MicIcon />
            </span>
            <span className="legal-pack-text">
              <strong>{L.say}</strong>
              <span className="hint">{L.sayHint}</span>
            </span>
            <ArrowRightIcon className="legal-pack-arrow" />
          </Link>

          <section className="fx-panel" aria-labelledby="consent-title">
            <h2 id="consent-title" className="fx-h2">
              {t("voice.consent_title")}
            </h2>
            <ul className="vx-langs">
              {allLangs("voice.consent_body").map((c) => (
                <li key={c.lang}>
                  <span className="vx-lang-tag">{LANG_TAG[c.lang] ?? c.lang}</span>
                  <p lang={c.lang === "te" ? "te" : c.lang === "hi-en" ? "hi" : "en"}>
                    {c.text}
                  </p>
                </li>
              ))}
            </ul>
            <p className="vx-lock">
              <LockIcon /> {t("voice.none")}
            </p>
            <Toggle
              checked={vp.consent}
              onChange={vp.setConsent}
              label={allLangs("voice.agree")
                .map((c) => c.text)
                .join(" · ")}
            />
          </section>

          {vp.justDeleted ? <p className="fx-muted">{t("voice.deleted")}</p> : null}

          {vp.consent ? (
            <section className="fx-panel vx-record">
              <p className="fx-eyebrow">{t("voice.say_this")}</p>
              <blockquote className="vx-script">{SAMPLE[lang] ?? SAMPLE.en}</blockquote>
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
              <div className="vx-progress" aria-hidden="true">
                <span style={{ width: `${Math.round(Math.min(1, vp.progress) * 100)}%` }} />
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      <ErrorNote message={vp.error === "consent_required" ? t("voice.consent_title") : vp.error} />
    </Screen>
  );
}
