// Baaki marketing website ("/"). Server components; the interactive bits (theme toggle, install
// button, phone demo, count-up) are small client islands. Styles: app/site.css. Copy rules: no
// legal outcomes, no recovery rates, every number credited, estimates labelled, demo marked synthetic.
// Positioning: a wage advocate in her pocket (money and outcomes first; language is the delivery).

import Link from "next/link";
import type { ReactNode } from "react";
import { Illustration, type IllustrationName } from "@/components/ui/Illustration";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { InstallButton } from "@/components/ui/InstallButton";
import { CountUp, StatusPill } from "@/components/ui/kit";
import { Logo } from "@/components/ui/Logo";
import {
  ArrowRightIcon,
  BellIcon,
  BotIcon,
  CheckIcon,
  DiaryIcon,
  FileIcon,
  HomeIcon,
  LanguageIcon,
  LockIcon,
  MicIcon,
  PhoneIcon,
  RupeeIcon,
  ShieldIcon,
  SparkIcon,
  WaveIcon,
} from "@/components/ui/icons";
import { PhoneDemo } from "./PhoneDemo";
import { Lakh, Percent } from "./Percent";

/** Where the "Am I paying my house help fairly?" teaser points. Change when the employer check ships. */
export const FAIR_CHECK_HREF = "/check";

const SIASAT_SURVEY = "https://www.siasat.com/the-silent-domestic-labour-force-in-telangana-is-mostly-invisible-3264044";
const SIASAT_COUNT = "https://www.siasat.com/we-want-dignity-domestic-workers-protest-for-rights-recognition-in-hyderabad-3234135/";

/** The positioning line, used across the site, the app and the submission. */
export const POSITIONING = "A wage advocate in her pocket. It knows the law, does the maths, asks for her, and keeps the proof.";

// ------------------------------------------------------------------ header
export function SiteHeader() {
  return (
    <header className="s-header">
      <div className="s-wrap s-header-row">
        <Link href="/" className="s-logo-link" aria-label="Baaki home">
          <Logo size={34} />
        </Link>
        <nav className="s-nav" aria-label="Sections">
          <a href="#outcomes">Outcomes</a>
          <a href="#problem">Problem</a>
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="#trust">Safety</a>
        </nav>
        <div className="s-header-actions">
          <ThemeToggle />
          <Link href="/app" className="btn btn-primary s-header-cta">
            Open app
          </Link>
        </div>
      </div>
    </header>
  );
}

// ------------------------------------------------------------------ hero
export function Hero() {
  return (
    <>
      <section className="s-hero" aria-labelledby="hero-title">
        <div className="s-hero-bg" aria-hidden="true">
          <span className="s-orb s-orb-1" />
          <span className="s-orb s-orb-2" />
          <span className="s-orb s-orb-3" />
          <span className="s-grid" />
        </div>
        <div className="s-wrap s-hero-grid">
          <div className="s-hero-copy">
            <StatusPill tone="accent" className="s-eyebrow">
              A wage advocate for Hyderabad’s house helps, cooks and cleaners
            </StatusPill>
            <h1 id="hero-title" className="s-display s-hero-title">
              ₹18,000 a year, missing from her pay.
              <br />
              <em className="grad-text">Baaki asks for it.</em>
            </h1>
            <p className="s-hero-fine">
              <StatusPill tone="estimate" dot={false}>
                estimate
              </StatusPill>
              <span>
                One part-time job: ₹2,500 a month for 2 hours a day, against about ₹4,000 under Telangana’s minimum wage
                (G.O.Ms.No.6, 2026).
              </span>
            </p>
            <p className="s-lede">
              <b>Baaki is a wage advocate in her pocket.</b> It knows the law, does the maths, asks for her, and keeps the proof.
              She just speaks, in Telugu or Hinglish, and the employer hears it in <em>theirs</em>.
            </p>
            <div className="s-cta-row">
              <Link href="/app" className="btn btn-primary btn-big s-cta">
                <MicIcon />
                <span>Open the app</span>
              </Link>
              <a href="#how" className="btn btn-big s-cta s-cta-ghost">
                <span>See how it works</span>
                <ArrowRightIcon />
              </a>
            </div>
            <ul className="s-ticks" aria-label="Promises">
              <li>
                <CheckIcon /> Every rupee checked against the law
              </li>
              <li>
                <CheckIcon /> Nothing is sent without her OK
              </li>
              <li>
                <CheckIcon /> Free, no reading needed
              </li>
            </ul>
            <InstallButton label="Install Baaki" className="s-install" />
          </div>
          <div className="s-hero-visual">
            <span className="s-float s-float-1" aria-hidden="true">
              <b className="grad-text">₹12,692</b>
              <small>owed by law · not ₹13,000</small>
            </span>
            <span className="s-float s-float-2" aria-hidden="true">
              <CheckIcon /> Baaki knows: only ₹308 cut allowed
            </span>
            <span className="s-float s-float-3" aria-hidden="true">
              <WaveIcon /> Asked for her, in Hinglish
            </span>
            <PhoneDemo />
          </div>
        </div>
      </section>
      <Outcomes />
    </>
  );
}

// ------------------------------------------------------------------ outcomes strip
function Outcomes() {
  return (
    <section id="outcomes" className="s-outcomes s-section" aria-labelledby="outcomes-title">
      <div className="s-wrap">
        <header className="s-outcomes-head">
          <h2 id="outcomes-title" className="s-kicker">
            What Baaki gets done
          </h2>
          <p className="s-outcomes-note">Demo names and amounts are fictional. Estimates are labelled.</p>
        </header>
        <ul className="s-outcome-list">
          <li className="s-outcome">
            <p className="s-outcome-value">
              <CountUp value={12692} durationMs={1400} />
            </p>
            <p className="s-outcome-label">Sharma ji’s baaki, asked for and paid</p>
            <p className="s-outcome-sub">She said ₹13,000. Baaki knew the law allows a ₹308 sick-day cut, not ₹1,000.</p>
            <StatusPill tone="neutral" dot={false}>
              synthetic demo
            </StatusPill>
          </li>
          <li className="s-outcome">
            <p className="s-outcome-value">
              <CountUp value={18000} durationMs={1400} />
              <small>/yr</small>
            </p>
            <p className="s-outcome-label">The raise one part-time job is short of</p>
            <p className="s-outcome-sub">₹2,500 → about ₹4,000 a month. Haq Raise asks for it, with a step-up plan.</p>
            <StatusPill tone="estimate" dot={false}>
              estimate
            </StatusPill>
          </li>
          <li className="s-outcome">
            <p className="s-outcome-value">
              2 <small>working days</small>
            </p>
            <p className="s-outcome-label">Final dues, if she’s let go</p>
            <p className="s-outcome-sub">The Exit Kit shows the exact date and her part-month pay (Code on Wages s.17(2)).</p>
            <StatusPill tone="neutral" dot={false}>
              the law
            </StatusPill>
          </li>
          <li className="s-outcome">
            <p className="s-outcome-value">
              34<small>/34</small>
            </p>
            <p className="s-outcome-label">Rupee amounts heard exactly, in kitchen noise</p>
            <p className="s-outcome-sub">24 noisy clips: stock voices, a synthetic kitchen, run once.</p>
            <StatusPill tone="neutral" dot={false}>
              small test
            </StatusPill>
          </li>
        </ul>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ problem
export function Problem() {
  return (
    <section id="problem" className="s-section s-problem" aria-labelledby="problem-title">
      <div className="s-wrap">
        <div className="s-problem-card">
          <span className="haze" aria-hidden="true" />
          <div className="s-problem-main">
            <p className="s-kicker">The problem</p>
            <p className="s-stat">
              <Percent value={81} />
            </p>
            <h2 id="problem-title" className="s-display s-problem-title">
              of Hyderabad’s domestic workers earn <em>below the minimum wage.</em>
            </h2>
            <p className="s-credit">
              2023 Montfort Social Institute survey, via{" "}
              <a href={SIASAT_SURVEY} target="_blank" rel="noreferrer">
                Siasat
              </a>
              .
            </p>
          </div>
          <div className="s-problem-side">
            <p className="s-problem-pitch">
              She can speak. <em>She just can’t safely ask.</em>
            </p>
            <p className="s-problem-quote">
              No contract. No payslip. Cash in hand, a month “adjusted” here and there. Asking means risking the job, often in a
              language the employer doesn’t speak. So the money stays unasked for, and nothing is in writing.
            </p>
            <dl className="s-mini-stats">
              <div>
                <dt>
                  <Percent value={68} />
                </dt>
                <dd>have never had a raise</dd>
              </div>
              <div>
                <dt>
                  <Percent value={96} />
                </dt>
                <dd>get no weekly day off</dd>
              </div>
              <div>
                <dt>
                  <Lakh value={6} />
                </dt>
                <dd>
                  domestic workers in Hyderabad (
                  <a href={SIASAT_COUNT} target="_blank" rel="noreferrer">
                    union estimate
                  </a>
                  )
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ how it works
const STEPS: { ill: IllustrationName; title: string; body: ReactNode; tag: string }[] = [
  {
    ill: "speak",
    tag: "Speak",
    title: "Say it, in your language",
    body: (
      <>
        Tap the mic and talk: <em lang="te">“మూడు నెలలు జీతం ఇవ్వలేదు…”</em> Telugu, Hindi or a mix. It works over a pressure-cooker whistle.
      </>
    ),
  },
  {
    ill: "coins",
    tag: "Know",
    title: "Baaki does the maths, by the law",
    body: "Every month, cut and advance adds up, then gets checked: a ₹1,000 cut for 2 sick days becomes ₹308 allowed, ₹692 back. She hears it read back and confirms.",
  },
  {
    ill: "send",
    tag: "Ask",
    title: "Baaki asks, so she doesn’t have to",
    body: "A polite voice note in the employer’s language, with an itemised card and the source for every number. She presses Send.",
  },
  {
    ill: "celebrate",
    tag: "Paid",
    title: "“Paisa aa gaya!”",
    body: "The employer pays by UPI in one tap, or in parts. Baaki tells her when it’s marked paid, and keeps the proof.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="s-section" aria-labelledby="how-title">
      <div className="s-wrap">
        <header className="s-section-head">
          <p className="s-kicker">How Baaki works</p>
          <h2 id="how-title" className="s-display s-h2">
            From a voice note to <em className="grad-text">money in hand</em>, in four steps.
          </h2>
        </header>
        <ol className="s-steps">
          {STEPS.map((s, i) => (
            <li key={s.tag} className="s-step" style={{ animationDelay: `${i * 80}ms` }}>
              <div className="s-step-art">
                <Illustration name={s.ill} animated />
              </div>
              <span className="s-step-num">
                {i + 1} · {s.tag}
              </span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ showcase phones
export function Showcase() {
  return (
    <section className="s-section s-showcase" aria-labelledby="showcase-title">
      <div className="s-wrap">
        <header className="s-section-head s-center">
          <p className="s-kicker">Baaki knows</p>
          <h2 id="showcase-title" className="s-display s-h2">
            She says ₹13,000. <em className="grad-text">The law says ₹12,692.</em>
          </h2>
          <p className="s-section-sub">Baaki never asks for more than the law supports, so her claim is hard to wave away.</p>
        </header>
        <div className="s-phones">
          <figure>
            <PhoneDemo scene="speak" />
            <figcaption>She says what she remembers</figcaption>
          </figure>
          <figure className="s-phones-mid">
            <PhoneDemo scene="knows" />
            <figcaption>Baaki checks every rupee against the law</figcaption>
          </figure>
          <figure>
            <PhoneDemo scene="send" />
            <figcaption>The employer gets the exact amount, and a pay button</figcaption>
          </figure>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ features
const FEATURES: { icon: ReactNode; title: string; body: string }[] = [
  { icon: <RupeeIcon />, title: "Haq Check", body: "Compares her pay with Telangana’s minimum wage (G.O.Ms.No.6, 2026) and shows the source. Part-time figures are marked as estimates." },
  { icon: <SparkIcon />, title: "Haq Raise", body: "Asks for a raise to the legal minimum, with a step-up plan the employer can live with. The employer taps Accept on their page." },
  { icon: <HomeIcon />, title: "Exit Kit", body: "Told “don’t come from tomorrow”? Baaki shows the date her final dues fall due (2 working days) and her part-month pay." },
  { icon: <BellIcon />, title: "Asks for her", body: "Polite, then firm, then a bilingual letter that points to free legal aid, in the employer’s language. She chooses every step." },
  { icon: <PhoneIcon />, title: "Pay in one tap", body: "The employer page plays the note, lists every item and opens UPI with the amount filled in. Paying in parts is fine too." },
  { icon: <DiaryIcon />, title: "Keeps the proof", body: "A 5-second daily voice diary, and every promise the employer makes, saved with the date and his own words." },
];

export function Features() {
  return (
    <section id="features" className="s-section" aria-labelledby="features-title">
      <div className="s-wrap">
        <header className="s-section-head">
          <p className="s-kicker">What her advocate does</p>
          <h2 id="features-title" className="s-display s-h2">
            Knows the law. Does the maths. <em className="grad-text">Asks for her. Keeps the proof.</em>
          </h2>
        </header>
        <ul className="s-features">
          {FEATURES.map((f) => (
            <li key={f.title} className="s-feature">
              <span className="s-feature-icon">{f.icon}</span>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ employer teaser
export function FairTeaser() {
  return (
    <section className="s-section" aria-labelledby="fair-title">
      <div className="s-wrap">
        <div className="s-fair">
          <div className="s-fair-copy">
            <p className="s-kicker">For employers</p>
            <h2 id="fair-title" className="s-display s-h2">
              Am I paying my house help <em className="grad-text">fairly?</em>
            </h2>
            <p>
              Hyderabad’s minimum for a full-time house help is <b>₹16,000 a month</b> (G.O.Ms.No.6, from 1 June 2026). For part-time
              work that is about <b>₹77 an hour</b>{" "}
              <StatusPill tone="estimate" dot={false}>
                our estimate
              </StatusPill>
              .
            </p>
            <Link href={FAIR_CHECK_HREF} className="btn btn-primary btn-big s-fair-cta">
              <span>Check in 30 seconds</span>
              <ArrowRightIcon />
            </Link>
          </div>
          <div className="s-fair-art">
            <Illustration name="handshake" animated />
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Gnani tech
const TECH: { name: string; what: string; how: string; icon: ReactNode }[] = [
  {
    icon: <MicIcon />,
    name: "Prisma speech-to-text",
    what: "Hears Telugu, Hindi and code-mixed speech",
    how: "Language is detected automatically, and it holds up in a noisy kitchen. Long voice notes are split into short clips.",
  },
  {
    icon: <WaveIcon />,
    name: "Timbre text-to-speech",
    what: "Reads numbers back slowly, with pauses",
    how: "The read-back, the employer’s voice note and the “Paisa aa gaya!” moment are all spoken in the listener’s language.",
  },
  {
    icon: <LanguageIcon />,
    name: "Voice cloning, with consent",
    what: "Her voice, their language",
    how: "Ten seconds of her voice, recorded once with clear consent. Without it, a standard Timbre voice is used.",
  },
];

export function GnaniTech() {
  return (
    <section className="s-section s-tech" aria-labelledby="tech-title">
      <div className="s-wrap">
        <header className="s-section-head s-center">
          <p className="s-kicker">Powered by Gnani.ai</p>
          <h2 id="tech-title" className="s-display s-h2">
            Indian voice AI, doing <em className="grad-text">only what it does reliably.</em>
          </h2>
          <p className="s-section-sub">
            Language is how Baaki reaches her; money is what it’s for. Transcribe, read back, speak: every money figure is
            worked out by plain rules, never guessed by an AI.
          </p>
        </header>
        <ul className="s-tech-grid">
          {TECH.map((t) => (
            <li key={t.name} className="s-tech-card">
              <span className="s-tech-icon">{t.icon}</span>
              <p className="s-tech-name">{t.name}</p>
              <h3>{t.what}</h3>
              <p>{t.how}</p>
            </li>
          ))}
        </ul>
        <p className="s-center s-proof-link">
          <Link href="/proof" className="btn">
            Tested in a noisy kitchen: 34 of 34 rupee amounts heard exactly. See every clip →
          </Link>
        </p>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ trust
const TRUST: { icon: ReactNode; title: string; body: ReactNode }[] = [
  {
    icon: <BotIcon />,
    title: "Every AI voice says it is AI",
    body: "Each voice note opens with a disclosure that Baaki made it, in her voice, with her permission.",
  },
  {
    icon: <CheckIcon />,
    title: "Nothing goes out without her",
    body: "Every fact is read back and confirmed, and she presses Send herself, every time. Baaki never calls anyone.",
  },
  {
    icon: <ShieldIcon />,
    title: "Safety comes first",
    body: (
      <>
        If she mentions being locked in, hurt, her ID being taken or a child working, Baaki stops and shows <a href="tel:181">181</a>,{" "}
        <a href="tel:112">112</a> and <a href="tel:1098">1098</a>. A quick-exit button switches to a plain recipe page.
      </>
    ),
  },
  {
    icon: <FileIcon />,
    title: "Not a lawyer",
    body: "Baaki shows the calculation and where each number comes from, then hands over to legal aid or the labour office. It is not legal advice.",
  },
  {
    icon: <LockIcon />,
    title: "Private by design",
    body: "Quick exit also clears this phone’s session. The demo uses only fictional names and amounts.",
  },
];

export function Trust() {
  return (
    <section id="trust" className="s-section" aria-labelledby="trust-title">
      <div className="s-wrap s-trust">
        <div className="s-trust-head">
          <p className="s-kicker">Safety, privacy and AI</p>
          <h2 id="trust-title" className="s-display s-h2">
            Built for the person <em className="grad-text">with the least power</em> in the room.
          </h2>
          <Illustration name="shield" animated className="s-trust-art" />
        </div>
        <ul className="s-trust-list">
          {TRUST.map((t) => (
            <li key={t.title}>
              <span className="s-trust-icon">{t.icon}</span>
              <div>
                <h3>{t.title}</h3>
                <p>{t.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ beyond house help
function BeyondHouseHelp() {
  return (
    <section className="s-section" aria-labelledby="beyond-title">
      <div className="s-wrap">
        <div className="s-beyond">
          <div className="s-beyond-copy">
            <p className="s-kicker">Beyond house help</p>
            <h2 id="beyond-title" className="s-display s-h2">
              Every rupee someone <em className="grad-text">promised her.</em>
            </h2>
            <p>
              The same Baaki keeps track of the milkman’s unpaid bill, the chit money that’s “coming this week”, and the loan a
              relative swore to return. Each promise is saved with the date and their words, and a polite reminder is ready when
              it slips.
            </p>
            <Link href="/dues" className="btn btn-big s-beyond-cta">
              <span>See who owes her</span>
              <ArrowRightIcon />
            </Link>
          </div>
          <ul className="s-beyond-list">
            <li>
              <span className="s-beyond-icon">
                <RupeeIcon />
              </span>
              <span>
                <b>Daily services</b>
                <span>Milk, newspaper, tiffin: the bill she delivered for but wasn’t paid.</span>
              </span>
            </li>
            <li>
              <span className="s-beyond-icon">
                <BellIcon />
              </span>
              <span>
                <b>Chit and promised money</b>
                <span>“Next week, pakka.” Baaki counts how many times that was said.</span>
              </span>
            </li>
            <li>
              <span className="s-beyond-icon">
                <FileIcon />
              </span>
              <span>
                <b>A record pack</b>
                <span>Every promise and reminder in one file, for a union, legal aid or a family elder.</span>
              </span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ final CTA + footer
export function FinalCta() {
  return (
    <>
      <BeyondHouseHelp />
      <section className="s-section" aria-labelledby="cta-title">
        <div className="s-wrap">
          <div className="s-final">
            <span className="haze" aria-hidden="true" />
            <Illustration name="wave" animated className="s-final-art" />
            <h2 id="cta-title" className="s-display s-h2">
              Bolo. <em className="grad-text">Baaki sambhal lega.</em>
            </h2>
            <p className="s-final-en">Just speak. Baaki asks.</p>
            <p className="s-vision">
              Today, Lakshmi’s salary. Tomorrow, the milkman’s bill and the chit money that’s “coming this week” for two years.{" "}
              <em>Same promise. Same Baaki.</em>
            </p>
            <div className="s-cta-row s-center-row">
              <Link href="/app" className="btn btn-primary btn-big s-cta">
                <MicIcon />
                <span>Open the app</span>
              </Link>
              <InstallButton label="Install Baaki" variant="pill" />
            </div>
            <p>Free, and runs in the phone’s browser. Add it to the home screen like an app.</p>
          </div>
        </div>
      </section>
    </>
  );
}

export function SiteFooter() {
  return (
    <footer className="s-footer">
      <div className="s-wrap s-footer-grid">
        <div>
          <Logo size={30} />
          <p className="s-footer-tag">{POSITIONING}</p>
          <p className="s-footer-tag">
            <span lang="te">బాకీ</span> / <span lang="hi">बाकी</span>: the money still owed.
          </p>
        </div>
        <nav aria-label="Footer">
          <Link href="/app">Open the app</Link>
          <a href="#how">How it works</a>
          <Link href="/safety">Get help</Link>
        </nav>
        <div className="s-footer-help">
          <p>In danger right now?</p>
          <p>
            <a href="tel:112">112</a> · <a href="tel:181">181 Women</a> · <a href="tel:1098">1098 Child</a>
          </p>
        </div>
      </div>
      <div className="s-wrap s-footer-base">
        <p>Made for the Gnani.ai Great Indian AI Internship Challenge, 2026. Baaki is not a lawyer and this is not legal advice.</p>
      </div>
    </footer>
  );
}
