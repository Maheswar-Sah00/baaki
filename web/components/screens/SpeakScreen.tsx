"use client";

// Speak (/speak): tap or hold the mic, see the transcript and the Baaki Meter count up, fix or remove
// amount chips, then continue to Confirm. "Type instead" works with no voice service at all.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useListen, useLiveMeter, usePressToTalk, useSafety, useSettings, useT } from "@/hooks";
import { draftStore } from "@/lib/store";
import type { ListenLang } from "@/lib/types";
import { BottomSheet, Card, ChipView, ErrorNote, GradientButton, MeterValue, MicButton, Screen } from "@/components/ui/primitives";
import { CheckIcon, MicIcon, WaveIcon } from "@/components/ui/icons";

/**
 * Live chunks while recording, so the meter moves while she talks. Each chunk is one Gnani STT call.
 * ON by default every 4500 ms. Set NEXT_PUBLIC_BAAKI_INTERIM_MS at build time to change the interval,
 * or to 0 / off to send only the final recording (scripts/start-demo.ps1 -NoInterim).
 */
const INTERIM_MS = interimSetting(process.env.NEXT_PUBLIC_BAAKI_INTERIM_MS);

function interimSetting(raw: string | undefined): number | null {
  const v = (raw ?? "").trim().toLowerCase();
  if (!v) return 4500;
  if (["0", "off", "false", "no"].includes(v)) return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= 2500 ? n : 4500; // useListen skips snapshots under 2.5 s anyway
}

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

  const editing = live.chips.find((c) => c.id === editingChip) ?? null;

  return (
    <Screen title={t("speak.title")} back="/app" t={t} className="speak-screen">
      <div className="segmented speak-langs" role="group" aria-label={t("lang.change")}>
        {LISTEN_LANGS.map((l) => (
          <button
            key={l.value}
            type="button"
            lang={l.value === "te" ? "te" : undefined}
            aria-pressed={settings.listenLang === l.value}
            onClick={() => settings.setListenLang(l.value)}
            disabled={listen.status === "recording"}
          >
            {t(l.key)}
          </button>
        ))}
      </div>

      <section
        className="speak-stage"
        data-state={listen.status}
        data-typing={typing}
        data-interim={listen.interimCount}
        aria-label={t("speak.meter")}
      >
        <span className="speak-stage-glow" aria-hidden="true" />
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
      </section>

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
                editing={false}
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

      <BottomSheet
        open={editing !== null}
        onClose={() => setEditingChip(null)}
        title={editing ? t(`chip.${editing.kind}` as Parameters<typeof t>[0]) : undefined}
        closeLabel={t("common.close")}
        className="chip-sheet"
      >
        {editing ? (
          <>
            {editing.text ? <p className="chip-sheet-said">&ldquo;{editing.text}&rdquo;</p> : null}
            <ChipView
              chip={editing}
              t={t}
              editing
              setEditing={(v) => setEditingChip(v ? editing.id : null)}
              onRemove={() => {
                setEditingChip(null);
                void live.removeChip(editing.id);
              }}
              onEdit={(v) => void live.editChip(editing.id, v)}
            />
          </>
        ) : null}
      </BottomSheet>

      {typing ? (
        <Card as="section" tone="soft" className="speak-type">
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
        </Card>
      ) : listen.transcript ? (
        <Card as="section" tone="soft" className="speak-transcript" aria-live="polite">
          <h2 className="card-title">
            <WaveIcon /> {t("speak.transcript")}
          </h2>
          <p className="transcript">{listen.transcript}</p>
        </Card>
      ) : null}

      <div className="actions speak-actions">
        {hasSomething ? (
          <GradientButton onClick={goConfirm} disabled={live.busy || listen.status === "listening"} icon={<CheckIcon />}>
            {t("speak.continue")}
          </GradientButton>
        ) : null}
        <div className="speak-secondary">
          {hasSomething ? (
            <button type="button" className="btn" onClick={again}>
              {t("speak.again")}
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-ghost"
            aria-pressed={typing}
            onClick={() => {
              if (!typing && listen.transcript && !live.text) live.fromText(listen.transcript, settings.listenLang);
              setTyping((v) => !v);
            }}
          >
            {typing ? <MicIcon /> : <KeyboardIcon />}
            {typing ? t("speak.tap") : t("speak.type")}
          </button>
        </div>
      </div>
    </Screen>
  );
}

function KeyboardIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2.5" y="6" width="19" height="12" rx="2.5" />
      <path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M7 14h10" />
    </svg>
  );
}
