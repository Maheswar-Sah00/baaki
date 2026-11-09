"use client";

// Noise proof page body (G04+V14): the headline number, one card per condition (each with the same
// sentence to hear), the hardest clip, every clip with play buttons (noisy and clean), what Prisma
// heard with amounts marked, the misses, and the method.
// 10 Nov 2026 redesign: Vyra-like sections. The number is the hero; everything below is evidence.

import { useEffect, useMemo, useState } from "react";
import { CountUp, PlayButton, Skeleton } from "@/components/ui/primitives";
import { CheckIcon, CrossIcon } from "@/components/ui/icons";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import {
  bySentence,
  fetchProof,
  inrPlain,
  runDate,
  segments,
  type ProofClip,
  type ProofCondition,
  type ProofData,
} from "@/lib/features/proof";

const HERO_CLIP = "hi03-combined"; // two amounts, Hinglish, the hardest condition
const TONES = ["sky", "peach", "lilac", "sage", "butter", "rose"];

type Player = ReturnType<typeof useAudioPlayer>;

function Transcript({ clip }: { clip: ProofClip }) {
  if (clip.error) return <p className="pf-err">Prisma call failed ({clip.error}). Not counted.</p>;
  const text = clip.transcript ?? "";
  if (!text) return <p className="pf-err">Prisma returned nothing.</p>;
  return (
    <p className="pf-transcript" lang={clip.lang === "te" ? "te" : "hi"}>
      {segments(text, clip.spans).map((p, i) =>
        p.span ? (
          <mark
            key={i}
            className={p.span.match ? "pf-hit" : "pf-miss"}
            title={p.span.match ? `${inrPlain(p.span.amount)}: exact` : `${inrPlain(p.span.amount)}: not what was said`}
          >
            {p.text}
            <span className="pf-mark-amt">
              {p.span.match ? <CheckIcon /> : <CrossIcon />}
              {inrPlain(p.span.amount)}
            </span>
          </mark>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </p>
  );
}

function AmountChips({ clip }: { clip: ProofClip }) {
  return (
    <span className="pf-chips">
      {clip.amounts.map((a, i) => (
        <span key={i} className={a.heard ? "pf-chip-ok" : "pf-chip-bad"}>
          {a.heard ? <CheckIcon /> : <CrossIcon />}
          {inrPlain(a.amount)}
          <span className="pf-sr-only">{a.heard ? " heard exactly" : " missed"}</span>
        </span>
      ))}
      {clip.extras.map((x, i) => (
        <span key={`x${i}`} className="pf-chip-bad" title="Heard but never said">
          <CrossIcon />+{inrPlain(x)}
        </span>
      ))}
    </span>
  );
}

function Play({ player, url, label, onPlay }: { player: Player; url: string; label: string; onPlay?: () => void }) {
  const active = player.isCurrent(url);
  return (
    <PlayButton
      state={player.state}
      active={active}
      progress={active ? player.progress : 0}
      onClick={() => {
        void player.toggle(url);
        onPlay?.();
      }}
      label={label}
    />
  );
}

/** One card per noise condition: the score as the hero numeral, a bar, the same sentence to hear. */
function Conditions({ per, sample, player }: { per: ProofCondition[]; sample: ProofClip[]; player: Player }) {
  return (
    <ul className="pf-conds" aria-label="Exact rupee amounts per condition">
      {per.map((p, i) => {
        const missed = p.amounts - p.exact;
        const okPct = p.amounts ? (100 * p.exact) / p.amounts : 0;
        const clip = sample.find((c) => c.condition === p.condition);
        return (
          <li key={p.condition} className="pf-cond-card" data-tone={TONES[i % TONES.length]}>
            <div className="pf-cond-media">
              <div className="pf-cond-top">
                <span className="pf-cond-num">{String(i + 1).padStart(2, "0")}</span>
                {p.snr_db !== null ? <span className="pf-tag">{p.snr_db} dB SNR</span> : <span className="pf-tag">no added noise</span>}
              </div>
              <p className="pf-cond-score">
                <span className="pf-cond-exact">{p.exact}</span>
                <span className="pf-cond-of">/{p.amounts}</span>
                <span className="pf-sr-only"> amounts exact</span>
              </p>
              <div
                className="pf-track"
                role="img"
                aria-label={`${p.label}: ${p.exact} of ${p.amounts} amounts exact, ${missed} missed, ${p.clips} clips`}
                title={`${p.exact} exact · ${missed} missed · ${p.clips} clips · median ${p.median_latency_s ?? "?"} s`}
              >
                <span className="pf-fill-ok" style={{ width: `${okPct}%` }} />
                {missed > 0 ? <span className="pf-fill-bad" style={{ width: `${100 - okPct}%` }} /> : null}
              </div>
              {clip ? (
                <div className="pf-cond-play">
                  <Play player={player} url={clip.audio_url} label={p.condition === "clean" ? "Hear it" : "Hear it noisy"} />
                </div>
              ) : null}
            </div>
            <div className="pf-cond-foot">
              <h3 className="pf-cond-label">{p.label}</h3>
              <p className="pf-cond-desc">{p.desc}</p>
              <p className="pf-cond-meta">
                {p.clips} clips
                {Object.entries(p.by_lang).map(([lg, v]) => ` · ${lg === "te" ? "Telugu" : "Hinglish"} ${v.exact}/${v.amounts}`)}
                {missed === 0 ? " · no misses" : ` · ${missed} missed`}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function HeroClip({ clip, player }: { clip: ProofClip; player: Player }) {
  const [tapped, setTapped] = useState(false);
  const [started, setStarted] = useState(false);
  const active = player.isCurrent(clip.audio_url);
  // what Prisma heard appears a third of the way into the noisy clip (or on a tap), then stays
  const revealed =
    tapped || (started && (!active || player.progress > 0.33 || player.state === "ended" || player.state === "error"));
  return (
    <article className="pf-hero-clip">
      <div className="pf-window-bar" aria-hidden="true">
        <span />
        <span />
        <span />
        <em>Hardest clip</em>
      </div>
      <div className="pf-hero-clip-body">
        <div className="pf-hero-col">
          <p className="pf-label">She said · {clip.lang_label}</p>
          <p className="pf-said">
            <span lang="hi" className="pf-said-big">
              {clip.text}
            </span>
            <span className="pf-gloss">{clip.gloss}</span>
          </p>
          <p className="pf-meta">{clip.condition_label}</p>
          <div className="pf-play-row">
            <Play player={player} url={clip.audio_url} label="Play noisy" onPlay={() => setStarted(true)} />
            <Play player={player} url={clip.clean_url} label="Play clean" />
          </div>
        </div>
        <div className="pf-hero-col pf-heard" data-revealed={revealed || undefined}>
          <p className="pf-label">Prisma heard</p>
          {revealed ? (
            <>
              <Transcript clip={clip} />
              <AmountChips clip={clip} />
            </>
          ) : (
            // at rest: the answer is veiled (a transcript-shaped placeholder), not an empty panel
            <div className="pf-veil">
              <div className="pf-veil-lines" aria-hidden="true">
                <span style={{ width: "94%" }} />
                <span style={{ width: "36%" }} className="pf-veil-amt" />
                <span style={{ width: "48%" }} />
                <span style={{ width: "30%" }} className="pf-veil-amt" />
                <span style={{ width: "70%" }} />
              </div>
              <button type="button" className="pf-reveal-btn" onClick={() => setTapped(true)}>
                Show what Prisma heard
              </button>
              <p className="pf-veil-hint">Or play the noisy clip: it appears a third of the way in.</p>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

/** Short names for the phone condition switcher (falls back to the full label). */
const SHORT_COND: Record<string, string> = { clean: "Quiet", kitchen_0db: "Kitchen", combined: "Phone + WA" };

function SentenceCard({ rows, player, showSlips }: { rows: ProofClip[]; player: Player; showSlips: boolean }) {
  const first = rows[0];
  const allOk = rows.every((r) => r.match);
  // Phones show one condition at a time (the hardest first); wider screens show all three.
  const [sel, setSel] = useState(rows.length - 1);
  return (
    <article className="pf-sentence">
      <header className="pf-sentence-head">
        <span className="pf-meta">
          {first.lang_label} · voice {first.voice}
        </span>
        <span className={allOk ? "pf-score pf-score-ok" : "pf-score pf-score-bad"}>
          {allOk ? <CheckIcon /> : <CrossIcon />}
          {rows.reduce((n, r) => n + r.hits, 0)}/{rows.reduce((n, r) => n + r.total, 0)} exact
        </span>
      </header>
      <p className="pf-said">
        <span lang={first.lang === "te" ? "te" : "hi"} className="pf-said-text">
          {first.text}
        </span>
        <span className="pf-gloss">{first.gloss}</span>
      </p>
      <p className="pf-expected">Said: {first.expected.map((a) => inrPlain(a)).join(" and ")}</p>
      {rows.length > 1 ? (
        <div className="pf-seg" role="group" aria-label="Condition">
          {rows.map((r, i) => (
            <button key={r.clip_id} type="button" className="pf-seg-btn" aria-pressed={i === sel} data-ok={r.match || undefined} onClick={() => setSel(i)}>
              {r.match ? <CheckIcon /> : <CrossIcon />}
              {SHORT_COND[r.condition] ?? r.condition_label}
            </button>
          ))}
        </div>
      ) : null}
      <ul className="pf-rows">
        {rows.map((r, i) => (
          <li key={r.clip_id} className="pf-row" data-ok={r.match || undefined} data-sel={i === sel}>
            <div className="pf-row-head">
              <span className="pf-row-label">
                {r.condition_label}
                {r.snr_db !== null && !r.condition_label.includes("dB") ? <span className="pf-row-snr"> · {r.snr_db} dB</span> : null}
              </span>
              <Play player={player} url={r.audio_url} label={r.condition === "clean" ? "Play" : "Play noisy"} />
            </div>
            <Transcript clip={r} />
            <div className="pf-row-foot">
              <AmountChips clip={r} />
              {r.latency_s !== null ? <span className="pf-meta">{r.latency_s.toFixed(1)} s</span> : null}
            </div>
            {showSlips && r.word_slips.length ? (
              <p className="pf-slips">
                Words heard differently:{" "}
                {r.word_slips.map((w, i) => (
                  <span key={i} className="pf-slip">
                    <del>{w.said || "∅"}</del> → <ins>{w.heard || "∅"}</ins>
                  </span>
                ))}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </article>
  );
}

type Filter = "all" | "te" | "hinglish" | "misses";

export function ProofView() {
  const [data, setData] = useState<ProofData | null>(null);
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [showSlips, setShowSlips] = useState(true);
  const player = useAudioPlayer();

  useEffect(() => {
    const ac = new AbortController();
    fetchProof(ac.signal)
      .then(setData)
      .catch((e) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) setFailed(true);
      });
    return () => ac.abort();
  }, []);

  const groups = useMemo(() => {
    const all = bySentence(data?.clips ?? []);
    if (filter === "te" || filter === "hinglish") return all.filter((g) => g.rows[0].lang === filter);
    if (filter === "misses") return all.filter((g) => g.rows.some((r) => !r.match));
    return all;
  }, [data, filter]);

  if (failed) {
    return (
      <div className="pf-wrap pf-page">
        <div className="pf-note pf-note-warn">The proof data could not load. Try again in a moment.</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="pf-wrap pf-page pf-loading" aria-busy="true">
        <Skeleton height={220} radius="var(--r-xl)" className="pf-skel" />
        <Skeleton height={140} radius="var(--r-xl)" className="pf-skel" />
        <Skeleton height={320} radius="var(--r-xl)" className="pf-skel" />
      </div>
    );
  }

  const sum = data.summary;
  const head = sum?.headline;
  const hero = data.clips.find((c) => c.clip_id === HERO_CLIP) ?? data.clips.find((c) => c.condition === "combined");
  const sample = hero ? data.clips.filter((c) => c.utt_id === hero.utt_id) : [];
  const missedAmounts = sum ? sum.overall.amounts - sum.overall.exact : 0;
  const allExact = !!sum && sum.per_condition.every((p) => p.exact === p.amounts);
  const voices = new Set(data.clips.map((c) => c.voice)).size;
  const sentences = new Set(data.clips.map((c) => c.utt_id)).size;
  const tested = runDate(data.run_dates?.[data.run_dates.length - 1] ?? data.generated_at);

  return (
    <div className="pf-page">
      {/* ------------------------------------------------ hero: the one number */}
      <section className="pf-hero" aria-labelledby="proof-title">
        <div className="pf-sky" aria-hidden="true" />
        <div className="pf-wrap pf-hero-copy">
          <p className="pf-kicker">
            <span className="pf-kicker-dot" aria-hidden="true" />
            Noise proof{tested ? ` · tested ${tested}` : ""}
          </p>
          {head ? (
            <>
              <h1 id="proof-title" className="pf-big">
                <CountUp value={head.exact} format={(n) => String(n)} durationMs={1200} />
                <span className="pf-big-of">
                  <span className="pf-sr-only"> of </span>
                  <span aria-hidden="true">/</span>
                  {head.amounts}
                </span>
              </h1>
              <p className="pf-lead">
                rupee amounts heard <em>exactly</em>
              </p>
              <p className="pf-sub">
                In {head.clips} noisy clips of Telugu and Hinglish.{head.hardest ? ` ${head.hardest.text}` : ""}
              </p>
              <div className="pf-pills">
                <span className={missedAmounts ? "pf-pill pf-pill-bad" : "pf-pill pf-pill-ok"}>
                  {missedAmounts ? <CrossIcon /> : <CheckIcon />}
                  {missedAmounts ? `${missedAmounts} amounts missed` : "0 amounts missed"}
                </span>
                <span className="pf-pill pf-pill-soft">
                  {sentences} sentences · {voices} voices · {sum?.overall.clips} transcripts
                </span>
              </div>
            </>
          ) : (
            <h1 id="proof-title" className="pf-big pf-big-empty">
              The noise test has not run yet.
            </h1>
          )}
        </div>
        {hero ? (
          <div className="pf-wrap pf-hero-window">
            <HeroClip clip={hero} player={player} />
          </div>
        ) : null}
      </section>

      {/* ------------------------------------------------ conditions */}
      {sum && sum.per_condition.length ? (
        <section className="pf-wrap pf-section" aria-labelledby="proof-bars">
          <div className="pf-section-head">
            <h2 id="proof-bars" className="pf-h2">
              {allExact ? (
                <>
                  Louder rooms, <em>same rupees.</em>
                </>
              ) : (
                <>
                  Condition by <em>condition.</em>
                </>
              )}
            </h2>
            <p className="pf-h2-sub">
              The same {sentences} sentences, made worse on purpose. Each card plays one of them in that condition.
            </p>
          </div>
          <Conditions per={sum.per_condition} sample={sample} player={player} />
        </section>
      ) : null}

      {/* ------------------------------------------------ misses */}
      {sum ? (
        <section className="pf-wrap pf-section" aria-labelledby="proof-misses">
          <div className="pf-section-head">
            <h2 id="proof-misses" className="pf-h2">
              The <em>misses.</em>
            </h2>
          </div>
          {sum.misses.length ? (
            <ul className="pf-miss-list">
              {sum.misses.map((m) => (
                <li key={m.clip_id} className="pf-note pf-note-warn">
                  <strong>{m.clip_id}</strong>: missed {m.missed.map(inrPlain).join(", ") || "nothing"}
                  {m.extras.length ? `; also heard ${m.extras.map(inrPlain).join(", ")}, which was never said` : ""}.
                  <span className="pf-miss-text">Prisma heard: {m.transcript || "(nothing)"}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="pf-no-miss">
              <p className="pf-no-miss-num" aria-hidden="true">
                0
              </p>
              <div>
                <p className="pf-no-miss-title">No rupee amount was missed in this run.</p>
                <p className="pf-no-miss-text">
                  Prisma did not get every word right: {sum.word_slips} words in {sum.clips_with_word_slips} clips came out
                  differently from the script (another spelling, English instead of Telugu, a wrong word). None of them was
                  an amount. They are all shown below.
                </p>
              </div>
            </div>
          )}
        </section>
      ) : null}

      {/* ------------------------------------------------ every clip */}
      {data.clips.length ? (
        <section className="pf-wrap pf-section" aria-labelledby="proof-clips">
          <div className="pf-clips-head">
            <h2 id="proof-clips" className="pf-h2">
              Every <em>clip.</em>
            </h2>
            <div className="pf-filters" role="group" aria-label="Filter clips">
              {(
                [
                  ["all", "All"],
                  ["te", "Telugu"],
                  ["hinglish", "Hinglish"],
                  ["misses", "Misses"],
                ] as [Filter, string][]
              ).map(([k, label]) => (
                <button key={k} type="button" className="pf-filter" aria-pressed={filter === k} onClick={() => setFilter(k)}>
                  {label}
                </button>
              ))}
              <span className="pf-filter-sep" aria-hidden="true" />
              <button type="button" className="pf-filter pf-toggle" aria-pressed={showSlips} onClick={() => setShowSlips((v) => !v)}>
                <span className="pf-toggle-box" aria-hidden="true">
                  <CheckIcon />
                </span>
                Word slips
              </button>
            </div>
          </div>
          {groups.length ? (
            <div className="pf-grid">
              {groups.map((g) => (
                <SentenceCard key={g.utt_id} rows={g.rows} player={player} showSlips={showSlips} />
              ))}
            </div>
          ) : (
            <div className="pf-note">Nothing to show: no clip in this run had a missed amount.</div>
          )}
        </section>
      ) : null}

      {/* ------------------------------------------------ method */}
      <section className="pf-wrap pf-section pf-method-sec" aria-labelledby="proof-method">
        <div className="pf-method-head">
          <h2 id="proof-method" className="pf-h2">
            How we <em>tested.</em>
          </h2>
          <p className="pf-meta">
            Model {data.model ?? "prisma-v3.0"}
            {data.calls?.stt != null ? ` · ${data.calls.stt} Prisma calls, ${data.calls.tts} Timbre calls` : ""}
            {tested ? ` · ${tested}` : ""} · synthetic sentences, fictional amounts.
          </p>
        </div>
        <div>
          <ol className="pf-method">
            {data.method.map((m, i) => (
              <li key={i}>
                <span className="pf-method-num" aria-hidden="true">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>{m}</span>
              </li>
            ))}
          </ol>
          {data.caveats.length ? (
            <div className="pf-caveats">
              <p className="pf-label">Caveats</p>
              <ul>
                {data.caveats.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
