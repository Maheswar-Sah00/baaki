"use client";

// Speak (/speak): tap or hold the mic, see the transcript and the Baaki Meter count up, fix or remove
// amount chips, then continue to Confirm. "Type instead" works with no voice service at all.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useListen, useLiveMeter, usePressToTalk, useSafety, useSettings, useT } from "@/hooks";
import { draftStore } from "@/lib/store";
import type { ListenLang } from "@/lib/types";
import { ChipView, ErrorNote, MeterValue, MicButton, Screen } from "@/components/ui/primitives";

/** Opt-in live chunks while recording (each one is a Gnani STT call). e.g. NEXT_PUBLIC_BAAKI_INTERIM_MS=4500 */
const INTERIM_MS = Number(process.env.NEXT_PUBLIC_BAAKI_INTERIM_MS) || null;

const LISTEN_LANGS: { value: ListenLang; key: "listen.auto" | "listen.te" | "listen.hinglish" }[] = [
  { value: "auto", key: "listen.auto" },
  { value: "te", key: "listen.te" },
  { value: "hinglish", key: "listen.hinglish" },
];

export function SpeakScreen() {
  const router = useRouter();
  const settings = useSettings();
  const { t } = useT();
  const live = useLiveMeter();
  const { raise: raiseSafety } = useSafety();
  const [typing, setTyping] = useState(false);
  const [editingChip, setEditingChip] = useState<string | null>(null);

  const listen = useListen({
    lang: settings.listenLang,
    interimMs: INTERIM_MS,
    onResult: (r) => live.load(r.meter, { text: r.transcript, lang: r.detected_language_code ?? settings.listenLang }),
    onSafety: (s) => {
      raiseSafety(s);
      router.push("/safety");
    },
  });
  const press = usePressToTalk(listen.recorder, { disabled: listen.status === "listening" });

  // Typed text can trip the safety switch too (keyword check in /meter).
  const typedFlag = live.safety?.flagged ? live.safety : null;
  useEffect(() => {
    if (typedFlag) {
      raiseSafety(typedFlag);
      router.push("/safety");
    }
  }, [typedFlag, raiseSafety, router]);

  const text = live.text || listen.transcript;
  const hasSomething = text.trim().length > 0;

  const micLabel =
    listen.status === "recording"
      ? t("speak.stop")
      : listen.status === "starting"
        ? t("speak.starting")
        : listen.status === "listening"
          ? t("speak.listening")
          : t("speak.tap");

  const goConfirm = () => {
    draftStore.set({
      transcript: text,
      listenLang: settings.listenLang,
      detectedLang: listen.detectedLang,
      chips: live.chips,
      summary: live.summary,
      chipsEdited: live.edited,
      caseId: null,
      createdAt: Date.now(),
    });
    router.push("/case/new");
  };

  const again = () => {
    listen.reset();
    live.reset();
    setEditingChip(null);
  };

  return (
    <Screen title={t("speak.title")} back="/app" t={t} className="speak-screen">
      <div className="segmented" role="group" aria-label={t("lang.change")}>
        {LISTEN_LANGS.map((l) => (
          <button
            key={l.value}
            type="button"
            aria-pressed={settings.listenLang === l.value}
            onClick={() => settings.setListenLang(l.value)}
            disabled={listen.status === "recording"}
          >
            {t(l.key)}
          </button>
        ))}
      </div>

      <MeterValue value={live.display} tick={live.tick} animating={live.animating} label={t("speak.meter")} />
      {live.formula ? <p className="meter-formula">{live.formula}</p> : null}

      {!typing ? (
        <>
          <MicButton
            state={listen.status === "listening" ? "busy" : listen.recorder.state}
            level={listen.level}
            elapsedMs={listen.elapsedMs}
            disabled={listen.status === "listening" || listen.status === "starting"}
            handlers={press}
            label={micLabel}
          />
          {listen.status === "idle" ? <p className="hint center">{t("speak.hold")}</p> : null}
        </>
      ) : null}

      <ErrorNote message={listen.error} />
      {listen.voiceDown ? <p className="hint">{t("speak.voice_down")}</p> : null}
      <ErrorNote message={live.error} />

      {live.amountChips.length || live.countChips.length ? (
        <section className="chips-section" aria-label={t("speak.meter")}>
          <p className="hint">{t("speak.meter_hint")}</p>
          <div className="chips">
            {live.chips.map((c) => (
              <ChipView
                key={c.id}
                chip={c}
                t={t}
                editing={editingChip === c.id}
                setEditing={(v) => setEditingChip(v ? c.id : null)}
                onRemove={() => {
                  setEditingChip(null);
                  void live.removeChip(c.id);
                }}
                onEdit={(v) => void live.editChip(c.id, v)}
              />
            ))}
          </div>
        </section>
      ) : null}

      {typing ? (
        <section className="card">
          <label className="field">
            <span className="field-label">{t("speak.type")}</span>
            <textarea
              className="input"
              rows={4}
              value={live.text}
              placeholder={t("speak.type_ph")}
              onChange={(e) => live.fromText(e.target.value, settings.listenLang)}
              autoFocus
            />
          </label>
        </section>
      ) : listen.transcript ? (
        <section className="card" aria-live="polite">
          <h2 className="card-title">{t("speak.transcript")}</h2>
          <p className="transcript">{listen.transcript}</p>
        </section>
      ) : null}

      <div className="actions">
        {hasSomething ? (
          <button type="button" className="btn btn-primary btn-big" onClick={goConfirm} disabled={live.busy || listen.status === "listening"}>
            {t("speak.continue")}
          </button>
        ) : null}
        <div className="row">
          {hasSomething ? (
            <button type="button" className="btn" onClick={again}>
              {t("speak.again")}
            </button>
          ) : null}
          <button
            type="button"
            className="btn"
            aria-pressed={typing}
            onClick={() => {
              if (!typing && listen.transcript && !live.text) live.fromText(listen.transcript, settings.listenLang);
              setTyping((v) => !v);
            }}
          >
            {typing ? t("speak.tap") : t("speak.type")}
          </button>
        </div>
      </div>
    </Screen>
  );
}
