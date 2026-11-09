"use client";

// /dues/new: pick a kind (illustrated tiles), say who owes, then speak or type what is owed. Chips and a running
// total appear as the parser reads the amounts (typing re-reads after a short pause; speech goes through Prisma).

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { CountUp, ErrorNote, GradientButton, Loading, MicButton, Screen } from "@/components/ui/primitives";
import { useRecorder, useT, type Recording } from "@/hooks";
import { shortDate } from "@/lib/format";
import {
  createDues,
  duesLang,
  parseDues,
  sttLang,
  type DuesKind,
  type DuesLang,
  type ParsedItem,
  type ParsedPromise,
} from "@/lib/features/dues";
import { DuesArt } from "./DuesArt";
import { Chips, NotAdvice } from "./parts";
import { duesStrings } from "./strings";
import css from "./dues.module.css";

const KINDS: DuesKind[] = ["vendor", "chit", "other"];
const LANGS: DuesLang[] = ["te-IN", "hi-en", "en"];

export function NewDuesScreen({ initialKind }: { initialKind?: DuesKind | null }) {
  const { t, lang } = useT();
  const S = duesStrings(lang);
  const router = useRouter();
  const [kind, setKind] = useState<DuesKind | null>(initialKind ?? null);
  const [party, setParty] = useState("");
  const [partyLang, setPartyLang] = useState<DuesLang>(() => duesLang(lang));
  const [owner, setOwner] = useState("");
  const [vpa, setVpa] = useState("");
  const [phone, setPhone] = useState("");
  const [mode, setMode] = useState<"speak" | "type">("speak");
  const [text, setText] = useState("");
  const [typedItems, setTypedItems] = useState<ParsedItem[]>([]);
  const [spokenItems, setSpokenItems] = useState<ParsedItem[]>([]);
  const [heard, setHeard] = useState<string | null>(null);
  const [promise, setPromise] = useState<ParsedPromise | null>(null);
  const [keepPromise, setKeepPromise] = useState(true);
  const [busy, setBusy] = useState<null | "reading" | "saving">(null);
  const [err, setErr] = useState<string | null>(null);
  const typedSeq = useRef(0);

  const items = [...spokenItems, ...typedItems];
  const total = items.reduce((s, i) => s + i.amount, 0);

  // Typing: re-read the amounts 450 ms after the last key (text only: no Gnani credits).
  useEffect(() => {
    if (!kind) return;
    const seq = ++typedSeq.current;
    const words = text.trim();
    const timer = window.setTimeout(async () => {
      if (!words) {
        setTypedItems([]);
        return;
      }
      try {
        const r = await parseDues({ text: words, kind, party, lang: "auto" });
        if (seq !== typedSeq.current) return;
        setTypedItems(r.items);
        if (r.promise) setPromise(r.promise);
      } catch {
        /* keep the last chips */
      }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [text, kind, party]);

  const onRecorded = useCallback(
    async (rec: Recording) => {
      if (!kind) return;
      setBusy("reading");
      setErr(null);
      try {
        const r = await parseDues({ audio: rec.blob, filename: rec.filename, kind, party, lang: sttLang(duesLang(lang)) });
        setHeard(r.transcript);
        if (!r.items.length) setErr(S.noAmount);
        setSpokenItems((prev) => [...prev, ...r.items]);
        if (r.promise) setPromise(r.promise);
      } catch {
        setErr(S.error);
      } finally {
        setBusy(null);
      }
    },
    [kind, party, lang, S.noAmount, S.error],
  );
  const recorder = useRecorder({ onRecorded, maxMs: 30_000 });

  async function save() {
    if (!kind || !items.length || !party.trim()) return;
    setBusy("saving");
    setErr(null);
    try {
      const v = await createDues({
        kind,
        party_name: party.trim(),
        party_lang: partyLang,
        party_phone: phone.trim() || null,
        owner_name: owner.trim(),
        owner_lang: duesLang(lang),
        owner_vpa: kind === "vendor" ? vpa.trim() || null : null,
        title: S.kinds[kind],
        items: items.map((i) => ({ label: i.label, amount: i.amount, item_key: i.item_key, month: i.month, source_text: i.source_text })),
        promise_text: promise && keepPromise ? promise.quote : null,
      });
      router.push(`/dues/${v.account.id}`);
    } catch {
      setErr(S.error);
      setBusy(null);
    }
  }

  if (!kind) {
    return (
      <Screen title={S.newTitle} back="/dues" t={t}>
        <h2 className="section-title">{S.pickKind}</h2>
        <div className={css.tiles}>
          {KINDS.map((k, i) => (
            <button key={k} type="button" className={`${css.tile} ${css.rise}`} style={{ animationDelay: `${i * 70}ms` }} onClick={() => setKind(k)}>
              <DuesArt kind={k} size={76} />
              <span>
                <span className={css.tileTitle} style={{ display: "block" }}>
                  {S.kinds[k]}
                </span>
                <span className={css.tileHint} style={{ display: "block" }}>
                  {S.kindHints[k]}
                </span>
              </span>
            </button>
          ))}
        </div>
        <NotAdvice S={S} />
      </Screen>
    );
  }

  const dl = duesLang(lang);
  return (
    <Screen title={S.kinds[kind]} back="/dues" t={t}>
      <button type="button" className={`${css.tile} ${css.rise}`} aria-pressed="true" onClick={() => setKind(null)}>
        <DuesArt kind={kind} size={56} />
        <span>
          <span className={css.tileTitle} style={{ display: "block" }}>
            {S.kinds[kind]}
          </span>
          <span className={css.tileHint} style={{ display: "block" }}>
            {S.kindHints[kind]}
          </span>
        </span>
      </button>

      <section className="stack" aria-label={S.whoOwes}>
        <label className="field">
          <span className="field-label">{S.partyName}</span>
          <input className="input" value={party} maxLength={80} placeholder={S.partyPlaceholder[kind]} onChange={(e) => setParty(e.target.value)} />
        </label>
        <div className="field">
          <span className="field-label">{S.partyLang}</span>
          <div className="segmented" role="group">
            {LANGS.map((l) => (
              <button key={l} type="button" aria-pressed={partyLang === l} onClick={() => setPartyLang(l)}>
                {S.langs[l]}
              </button>
            ))}
          </div>
        </div>
        <div className={css.twoCol}>
          <label className="field">
            <span className="field-label">{S.yourName}</span>
            <input className="input" value={owner} maxLength={80} onChange={(e) => setOwner(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">{S.phone}</span>
            <input className="input" value={phone} inputMode="tel" maxLength={20} onChange={(e) => setPhone(e.target.value)} />
          </label>
        </div>
        {kind === "vendor" ? (
          <label className="field">
            <span className="field-label">{S.yourUpi}</span>
            <input className="input" value={vpa} maxLength={80} placeholder="name@bank" onChange={(e) => setVpa(e.target.value)} />
            <span className="hint">{S.upiHint}</span>
          </label>
        ) : null}
      </section>

      <section className="stack" aria-label={S.sayWhat}>
        <h2 className="section-title">{S.sayWhat}</h2>
        <p className="hint">{S.sayHint[kind]}</p>
        <div className="segmented" role="group">
          <button type="button" aria-pressed={mode === "speak"} onClick={() => setMode("speak")}>
            {S.tabSpeak}
          </button>
          <button type="button" aria-pressed={mode === "type"} onClick={() => setMode("type")}>
            {S.tabType}
          </button>
        </div>
        {mode === "speak" ? (
          <MicButton
            state={recorder.state}
            level={recorder.level}
            elapsedMs={recorder.elapsedMs}
            disabled={busy !== null}
            handlers={{ onClick: recorder.toggle }}
            label={recorder.state === "recording" ? S.recordStop : S.recordStart}
          />
        ) : (
          <textarea className="input" rows={3} value={text} maxLength={2000} placeholder={S.typePlaceholder[kind]} onChange={(e) => setText(e.target.value)} />
        )}
        <ErrorNote message={recorder.error} />
        {busy === "reading" ? <Loading label={S.reading} /> : null}
        {heard ? <p className={css.heard}>{S.heard(heard)}</p> : null}

        <div className={css.meter} aria-live="polite">
          <p className={css.eyebrow}>{S.runningTotal}</p>
          <p className={css.big}>
            <CountUp key={total} value={total} durationMs={700} />
          </p>
          {items.length ? <p className="hint">{S.tapToFix}</p> : null}
        </div>
        {items.length ? (
          <Chips
            items={items}
            lang={lang}
            S={S}
            onChange={(next) => {
              setSpokenItems(next.slice(0, Math.min(spokenItems.length, next.length)));
              setTypedItems(next.slice(Math.min(spokenItems.length, next.length)));
            }}
          />
        ) : null}
        {promise ? (
          <label className={css.promiseFound}>
            <input type="checkbox" checked={keepPromise} onChange={(e) => setKeepPromise(e.target.checked)} />
            <span>
              {S.promiseHeard(shortDate(promise.due_date, lang))} · {S.savePromiseToo}
            </span>
          </label>
        ) : null}
      </section>

      <ErrorNote message={err} />
      <GradientButton onClick={() => void save()} disabled={!items.length || !party.trim() || busy !== null}>
        {busy === "saving" ? S.saving : S.save}
      </GradientButton>
      <p className="hint" lang={dl === "te-IN" ? "te" : dl === "hi-en" ? "hi" : "en"}>
        {S.youSend}
      </p>
      <NotAdvice S={S} />
    </Screen>
  );
}
