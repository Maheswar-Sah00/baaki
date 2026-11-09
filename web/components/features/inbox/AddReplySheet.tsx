"use client";

// Add the employer's WhatsApp reply: upload the voice note (the main path: WhatsApp > Share > save, pick the
// file), record it playing on speaker, or paste the text. The PWA share target is a later add-on to this.

import { useCallback, useState } from "react";
import { BottomSheet, ErrorNote, Loading, MicButton } from "@/components/ui/primitives";
import { FileIcon } from "@/components/ui/icons";
import { useRecorder, formatTimer, type Recording } from "@/hooks";
import { todayIst } from "@/lib/format";
import { addReply, InboxError, type InboxAdded, type ReplyLang } from "@/lib/features/inbox";
import type { InboxStrings } from "./strings";
import css from "./inbox.module.css";

type Mode = "upload" | "record" | "paste";
const ACCEPT = "audio/*,.opus,.ogg,.oga,.m4a,.mp3,.aac,.amr,.3gp,.wav,.webm";

export function AddReplySheet({
  open,
  onClose,
  caseId,
  S,
  onAdded,
  initialFile,
  initialText,
}: {
  open: boolean;
  onClose: () => void;
  caseId: number;
  S: InboxStrings;
  onAdded: (r: InboxAdded) => void;
  initialFile?: File | null;
  initialText?: string | null;
}) {
  const [mode, setMode] = useState<Mode>(initialText ? "paste" : "upload");
  const [file, setFile] = useState<File | null>(initialFile ?? null);
  const [rec, setRec] = useState<Recording | null>(null);
  const [text, setText] = useState(initialText ?? "");
  const [lang, setLang] = useState<ReplyLang>("employer");
  const [saidOn, setSaidOn] = useState<string>(() => todayIst());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const recorder = useRecorder({ onRecorded: useCallback((r: Recording) => setRec(r), []), maxMs: 90_000 });

  const ready = (mode === "upload" && !!file) || (mode === "record" && !!rec) || (mode === "paste" && text.trim().length > 0);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const out = await addReply(caseId, {
        audio: mode === "upload" ? file : mode === "record" ? rec?.blob ?? null : null,
        filename: mode === "upload" ? file?.name : rec?.filename,
        text: mode === "paste" ? text.trim() : undefined,
        lang,
        saidOn,
      });
      onAdded(out);
      setFile(null);
      setRec(null);
      setText("");
      onClose();
    } catch (e) {
      setErr(e instanceof InboxError && e.message && !/^\d+$/.test(e.message) ? e.message : S.error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <BottomSheet open={open} onClose={busy ? () => undefined : onClose} title={S.sheetTitle} closeLabel={S.cancel}>
      <div className={css.sheetBody}>
        <div className="segmented" role="group">
          {(["upload", "record", "paste"] as Mode[]).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)} disabled={busy}>
              {m === "upload" ? S.tabUpload : m === "record" ? S.tabRecord : S.tabPaste}
            </button>
          ))}
        </div>

        {mode === "upload" ? (
          <div className="stack">
            <p className="hint">{S.uploadHint}</p>
            <label className={css.fileLabel}>
              <input
                className={css.fileInput}
                type="file"
                accept={ACCEPT}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                disabled={busy}
              />
              <FileIcon /> {file ? S.chosen(file.name) : S.chooseFile}
            </label>
          </div>
        ) : null}

        {mode === "record" ? (
          <div className={css.recorder}>
            <p className="hint">{S.recordHint}</p>
            <MicButton
              state={recorder.state}
              level={recorder.level}
              elapsedMs={recorder.elapsedMs}
              size="small"
              disabled={busy}
              handlers={{ onClick: recorder.toggle }}
              label={recorder.state === "recording" ? S.recordStop : rec ? S.recorded(formatTimer(rec.durationMs)) : S.recordStart}
            />
            <ErrorNote message={recorder.error} />
          </div>
        ) : null}

        {mode === "paste" ? (
          <textarea
            className="input"
            rows={4}
            value={text}
            maxLength={4000}
            placeholder={S.pastePlaceholder}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
          />
        ) : null}

        <div className={css.twoCol}>
          <label className="field">
            <span className="field-label">{S.langLabel}</span>
            <select className="input" value={lang} onChange={(e) => setLang(e.target.value as ReplyLang)} disabled={busy}>
              {(["employer", "auto", "hi-en", "te-IN", "en"] as ReplyLang[]).map((l) => (
                <option key={l} value={l}>
                  {S.langs[l]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">{S.saidOnLabel}</span>
            <input
              className="input"
              type="date"
              value={saidOn}
              max={todayIst()}
              onChange={(e) => setSaidOn(e.target.value)}
              disabled={busy}
            />
          </label>
        </div>

        {busy ? <Loading label={S.working} /> : null}
        <ErrorNote message={err} />
        <button type="button" className="btn btn-primary btn-big" disabled={!ready || busy} onClick={() => void submit()}>
          {S.submit}
        </button>
        <p className="hint">{S.privacy}</p>
      </div>
    </BottomSheet>
  );
}
