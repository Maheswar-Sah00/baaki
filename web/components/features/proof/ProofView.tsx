"use client";

// Noise proof page body (G04+V14): the headline number, one bar per condition, every clip with play
// buttons (noisy and clean), what Prisma heard with amounts marked, the misses, and the method.

import { useEffect, useMemo, useState } from "react";
import { Card, CountUp, PlayButton, Skeleton, StatusPill } from "@/components/ui/primitives";
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

function Bars({ per }: { per: ProofCondition[] }) {
  return (
    <ul className="pf-bars" aria-label="Exact rupee amounts per condition">
      {per.map((p) => {
        const missed = p.amounts - p.exact;
        const okPct = p.amounts ? (100 * p.exact) / p.amounts : 0;
        return (
          <li key={p.condition} className="pf-bar-row">
            <div className="pf-bar-head">
              <span className="pf-bar-label">
                {p.label}
                {p.snr_db !== null ? <span className="pf-bar-snr"> · {p.snr_db} dB SNR</span> : null}
              </span>
              <span className="pf-bar-value">
                <strong>{p.exact}</strong> of {p.amounts} exact
              </span>
            </div>
            <div
              className="pf-track"
              role="img"
              aria-label={`${p.label}: ${p.exact} of ${p.amounts} amounts exact, ${missed} missed, ${p.clips} clips`}
              title={`${p.exact} exact · ${missed} missed · ${p.clips} clips · median ${p.median_latency_s ?? "?"} s`}
            >
              <span className="pf-fill-ok" style={{ width: `${okPct}%` }} />
              {missed > 0 ? <span className="pf-fill-bad" style={{ width: `${100 - okPct}%` }} /> : null}
            </div>
            <p className="pf-bar-desc">
              {p.desc} {p.clips} clips
              {Object.entries(p.by_lang).map(([lg, v]) => ` · ${lg === "te" ? "Telugu" : "Hinglish"} ${v.exact}/${v.amounts}`)}
              {missed === 0 ? " · no misses" : ` · ${missed} missed`}
            </p>
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
    <Card tone="glow" className="pf-hero-clip">
      <div className="pf-hero-clip-head">
        <StatusPill tone="live">Hardest clip</StatusPill>
        <span className="pf-meta">
          {clip.lang_label} · {clip.condition_label}
        </span>
      </div>
      <p className="pf-said">
        <span className="pf-label">She said</span>
        <span lang="hi">{clip.text}</span>
        <span className="pf-gloss">{clip.gloss}</span>
      </p>
      <div className="pf-play-row">
        <Play player={player} url={clip.audio_url} label="Play noisy" onPlay={() => setStarted(true)} />
        <Play player={player} url={clip.clean_url} label="Play clean" />
      </div>
      <div className="pf-heard" data-revealed={revealed || undefined}>
        <span className="pf-label">Prisma heard</span>
        {revealed ? (
          <>
            <Transcript clip={clip} />
            <AmountChips clip={clip} />
          </>
        ) : (
          <button type="button" className="pf-reveal-btn" onClick={() => setTapped(true)}>
            Play it, or tap to see what Prisma heard
          </button>
        )}
      </div>
    </Card>
  );
}

function SentenceCard({ rows, player, showSlips }: { rows: ProofClip[]; player: Player; showSlips: boolean }) {
  const first = rows[0];
  const allOk = rows.every((r) => r.match);
  return (
    <Card as="article" className="pf-sentence">
      <header className="pf-sentence-head">
        <span className="pf-meta">
          {first.lang_label} · voice {first.voice}
        </span>
        <StatusPill tone={allOk ? "success" : "error"}>
          {rows.reduce((n, r) => n + r.hits, 0)}/{rows.reduce((n, r) => n + r.total, 0)} exact
        </StatusPill>
      </header>
      <p className="pf-said">
        <span lang={first.lang === "te" ? "te" : "hi"} className="pf-said-text">
          {first.text}
        </span>
        <span className="pf-gloss">{first.gloss}</span>
      </p>
      <p className="pf-expected">
        Said: {first.expected.map((a) => inrPlain(a)).join(" and ")}
      </p>
      <ul className="pf-cond-list">
        {rows.map((r) => (
          <li key={r.clip_id} className="pf-cond" data-ok={r.match || undefined}>
            <div className="pf-cond-head">
              <span className="pf-cond-label">
                {r.condition_label}
                {r.snr_db !== null ? <span className="pf-bar-snr"> · {r.snr_db} dB</span> : null}
              </span>
              <Play player={player} url={r.audio_url} label={r.condition === "clean" ? "Play" : "Play noisy"} />
            </div>
            <Transcript clip={r} />
            <div className="pf-cond-foot">
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
    </Card>
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
      <div className={`s-wrap pf-page`}>
        <Card tone="warn">The proof data could not load. Try again in a moment.</Card>
      </div>
    );
  }
  if (!data) {
    return (
      <div className={`s-wrap pf-page`} aria-busy="true">
        <Skeleton height={160} radius="var(--r-lg)" className="pf-skel" />
        <Skeleton height={120} radius="var(--r-lg)" className="pf-skel" />
        <Skeleton height={320} radius="var(--r-lg)" className="pf-skel" />
      </div>
    );
  }

  const sum = data.summary;
  const head = sum?.headline;
  const hero = data.clips.find((c) => c.clip_id === HERO_CLIP) ?? data.clips.find((c) => c.condition === "combined");
  const missedAmounts = sum ? sum.overall.amounts - sum.overall.exact : 0;
  const voices = new Set(data.clips.map((c) => c.voice)).size;
  const sentences = new Set(data.clips.map((c) => c.utt_id)).size;
  const tested = runDate(data.run_dates?.[data.run_dates.length - 1] ?? data.generated_at);

  return (
    <div className={`s-wrap pf-page`}>
      {/* ------------------------------------------------ hero */}
      <section className="pf-hero" aria-labelledby="proof-title">
        <div className="pf-hero-copy">
          <p className="s-kicker">Noise proof{tested ? ` · tested ${tested}` : ""}</p>
          {head ? (
            <>
              <h1 id="proof-title" className={`s-display pf-big`}>
                <CountUp value={head.exact} format={(n) => String(n)} durationMs={1200} />
                <span className="pf-big-of"> of {head.amounts}</span>
              </h1>
              <p className="pf-lead">
                rupee amounts heard <em className="grad-text">exactly</em>, in {head.clips} noisy clips of Telugu and
                Hinglish.
              </p>
              {head.hardest ? <p className="pf-sub">{head.hardest.text}</p> : null}
              <div className="pf-pills">
                <StatusPill tone={missedAmounts ? "error" : "success"}>
                  {missedAmounts ? `${missedAmounts} amounts missed` : "0 amounts missed"}
                </StatusPill>
                <StatusPill tone="neutral" dot={false}>
                  {sentences} sentences · {voices} voices · {sum?.overall.clips} transcripts
                </StatusPill>
              </div>
            </>
          ) : (
            <h1 id="proof-title" className={`s-display pf-big`}>
              The noise test has not run yet.
            </h1>
          )}
        </div>
        {hero ? <HeroClip clip={hero} player={player} /> : null}
      </section>

      {sum && sum.per_condition.length ? (
        <section className="pf-section" aria-labelledby="proof-bars">
          <h2 id="proof-bars" className={`s-display pf-h2`}>
            Condition by condition
          </h2>
          <Bars per={sum.per_condition} />
        </section>
      ) : null}

      {/* ------------------------------------------------ misses */}
      {sum ? (
        <section className="pf-section" aria-labelledby="proof-misses">
          <h2 id="proof-misses" className={`s-display pf-h2`}>
            The misses
          </h2>
          {sum.misses.length ? (
            <ul className="pf-miss-list">
              {sum.misses.map((m) => (
                <li key={m.clip_id}>
                  <Card tone="warn">
                    <strong>{m.clip_id}</strong>: missed {m.missed.map(inrPlain).join(", ") || "nothing"}
                    {m.extras.length ? `; also heard ${m.extras.map(inrPlain).join(", ")}, which was never said` : ""}.
                    <span className="pf-miss-text">Prisma heard: {m.transcript || "(nothing)"}</span>
                  </Card>
                </li>
              ))}
            </ul>
          ) : (
            <Card tone="success" className="pf-no-miss">
              <p>
                <strong>No rupee amount was missed in this run.</strong> Prisma did not get every word right:{" "}
                {sum.word_slips} words in {sum.clips_with_word_slips} clips came out differently from the script
                (another spelling, English instead of Telugu, a wrong word). None of them was an amount. They are all
                shown below.
              </p>
            </Card>
          )}
        </section>
      ) : null}

      {/* ------------------------------------------------ every clip */}
      {data.clips.length ? (
        <section className="pf-section" aria-labelledby="proof-clips">
          <div className="pf-clips-head">
            <h2 id="proof-clips" className={`s-display pf-h2`}>
              Every clip
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
              <button type="button" className="pf-filter" aria-pressed={showSlips} onClick={() => setShowSlips((v) => !v)}>
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
            <Card className="pf-empty">Nothing to show: no clip in this run had a missed amount.</Card>
          )}
        </section>
      ) : null}

      {/* ------------------------------------------------ method */}
      <section className="pf-section" aria-labelledby="proof-method">
        <h2 id="proof-method" className={`s-display pf-h2`}>
          How we tested
        </h2>
        <ol className="pf-method">
          {data.method.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ol>
        <ul className="pf-caveats">
          {data.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
        <p className="pf-meta">
          Model {data.model ?? "prisma-v3.0"}
          {data.calls?.stt != null ? ` · ${data.calls.stt} Prisma calls, ${data.calls.tts} Timbre calls` : ""}
          {tested ? ` · ${tested}` : ""} · synthetic sentences, fictional amounts.
        </p>
      </section>
    </div>
  );
}
