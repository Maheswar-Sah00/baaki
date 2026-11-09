// Baaki marketing website ("/"), Vyra-style: floating pill nav, painted-sky hero, a live Baaki
// workspace window, 01/02/03 cards, "what Baaki can do", every side of the conversation, proof,
// safety, FAQ. Server components with small client islands. Styles: app/site.css (.s-* / .ws-* /
// .cd-*). Copy rules: no legal outcomes, no recovery rates, every number from the code or a cited
// source, estimates labelled, demo names fictional.

import Link from "next/link";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { Logo, LogoMark } from "@/components/ui/Logo";
import {
  ArrowRightIcon,
  BotIcon,
  CheckIcon,
  CrossIcon,
  FileIcon,
  LockIcon,
  MicIcon,
  PlayIcon,
  ShieldIcon,
} from "@/components/ui/icons";
import { CanDo } from "./CanDo";
import { HeaderShell } from "./HeaderShell";
import { InstallCta } from "./InstallCta";
import { SiteMenu } from "./SiteMenu";
import { TypeLoop } from "./TypeLoop";
import { Workspace } from "./Workspace";

/** Where the "Am I paying my house help fairly?" teaser points. */
export const FAIR_CHECK_HREF = "/check";

const SIASAT_SURVEY = "https://www.siasat.com/the-silent-domestic-labour-force-in-telangana-is-mostly-invisible-3264044";

/** The positioning line, used across the site, the app and the submission. */
export const POSITIONING = "A wage advocate in her pocket. It knows the law, does the maths, asks for her, and keeps the proof.";

/** A supplied flat illustration (transparent WebP in /public/assets), shown only when its file exists
 *  (`art`, checked on the server by app/page.tsx). Decorative: the copy beside it says the same. */
function Art({ name, art, w, h, className }: { name: string; art?: string[]; w: number; h: number; className: string }) {
  if (!art?.includes(name)) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={`s-art ${className}`} src={`/assets/${name}.webp`} width={w} height={h} alt="" loading="lazy" decoding="async" />;
}

// ------------------------------------------------------------------ header
const NAV = [
  { href: "#how", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#interfaces", label: "Employers" },
  { href: "#proof", label: "Proof" },
  { href: "#trust", label: "Safety" },
];

export function SiteHeader() {
  return (
    <HeaderShell>
      <div className="s-header-row s-header-wide">
        <Link href="/" className="s-logo-link" aria-label="Baaki home">
          <Logo size={32} />
        </Link>
        <nav className="s-nav" aria-label="Sections">
          {NAV.map((l) => (
            <a key={l.href} href={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
        <div className="s-header-actions">
          <ThemeToggle />
          <InstallCta label="Install app" variant="link" className="s-header-install" />
          <Link href="/app" className="s-pill s-pill-ink s-header-cta">
            Open Baaki
          </Link>
          <SiteMenu links={NAV} />
        </div>
      </div>
    </HeaderShell>
  );
}

// ------------------------------------------------------------------ hero + workspace
export function Hero() {
  return (
    <section className="s-top" aria-labelledby="hero-title">
      <div className="s-sky" aria-hidden="true" />
      <div className="s-hero">
        <h1 id="hero-title" className="s-hero-title">
          <span className="s-hero-l1">Say what’s owed.</span>
          <span className="s-hero-l2">Baaki asks for it.</span>
        </h1>
        <p className="s-hero-sub">
          Speak in Telugu or Hinglish. Baaki works out every rupee owed under Telangana’s minimum wage, then asks the employer
          politely, in their own language.
        </p>
        <div className="s-hero-ctas">
          <Link href="/app" className="s-pill s-pill-soft s-pill-lg">
            <MicIcon />
            <span>Open Baaki</span>
          </Link>
          <InstallCta label="Install on your phone" className="s-pill-lg" />
        </div>
        <p className="s-hero-proof">
          <Link href="/proof">
            <b>34 of 34</b> rupee amounts heard exactly in kitchen noise
          </Link>
          <span className="s-sep" aria-hidden="true">
            ·
          </span>
          <span>Built on Gnani Prisma + Timbre</span>
        </p>
      </div>
      <div className="s-ws-wrap" id="demo">
        <Workspace />
        <p className="s-ws-note">Synthetic demo: Lakshmi, her three homes and every amount are fictional, taken from the app’s demo data.</p>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ problem statement
export function Problem() {
  return (
    <section id="problem" className="s-section s-problem" aria-labelledby="problem-title">
      <div className="s-wrap s-problem-inner">
        <h2 id="problem-title" className="s-statement">
          <span className="s-statement-num">81%</span>{" "}
          of Hyderabad’s domestic workers earn below the minimum wage. <em>She can speak. She just can’t safely ask.</em>
        </h2>
        <p className="s-credit">
          2023 Montfort Social Institute survey, via{" "}
          <a href={SIASAT_SURVEY} target="_blank" rel="noreferrer">
            Siasat
          </a>
          . No contract, no payslip, cash in hand, and the employer often speaks another language.
        </p>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ 01 / 02 / 03
export function HowItWorks() {
  return (
    <section id="how" className="s-section" aria-labelledby="how-title">
      <div className="s-wrap">
        <header className="s-head">
          <h2 id="how-title" className="s-h2">
            Three steps. <em>No reading needed.</em>
          </h2>
          <p className="s-sub">From a voice note to a polite, exact ask, in the employer’s language.</p>
        </header>
        <ol className="s-steps">
          <li className="s-step">
            <div className="s-step-head">
              <span className="s-step-num">01</span>
              <span className="s-step-word">Speak</span>
            </div>
            <div className="s-step-art" aria-hidden="true">
              <div className="st-speak">
                <span className="st-pill">
                  <i className="st-live" /> Listening · తెలుగు
                </span>
                <p className="st-transcript">
                  <TypeLoop text="శర్మ గారు మూడు నెలలు జీతం ఇవ్వలేదు…" lang="te" />
                </p>
                <p className="st-gloss">“Sharma garu hasn’t paid for three months…”</p>
                <span className="st-mic">
                  <span className="st-ring" />
                  <span className="st-mic-btn">
                    <MicIcon />
                  </span>
                </span>
              </div>
            </div>
            <h3>Say it, in your language</h3>
            <p>Telugu, Hindi or a mix. Tap the mic and talk; it holds up over a pressure-cooker whistle.</p>
          </li>
          <li className="s-step">
            <div className="s-step-head">
              <span className="s-step-num">02</span>
              <span className="s-step-word">Check</span>
            </div>
            <div className="s-step-art" aria-hidden="true">
              <div className="st-card st-readback">
                <span className="st-kicker">Baaki reads it back</span>
                <dl>
                  <div>
                    <dt>Aug – Oct wages</dt>
                    <dd>₹12,000</dd>
                  </div>
                  <div>
                    <dt>Sick-day cut</dt>
                    <dd>
                      <s>₹1,000</s> ₹308 allowed
                    </dd>
                  </div>
                  <div className="st-total">
                    <dt>Baaki’s calculation</dt>
                    <dd>₹12,692</dd>
                  </div>
                </dl>
                <p className="st-q" lang="te">
                  సరేనా? <span>Correct?</span>
                </p>
                <div className="st-yn">
                  <span className="st-yes">
                    <CheckIcon /> అవును
                  </span>
                  <span className="st-no">
                    <CrossIcon /> Fix
                  </span>
                </div>
              </div>
            </div>
            <h3>Baaki does the maths, with the source</h3>
            <p>Every month and every cut, checked against G.O.Ms.No.6 and the Code on Wages, then read back for her OK.</p>
          </li>
          <li className="s-step">
            <div className="s-step-head">
              <span className="s-step-num">03</span>
              <span className="s-step-word">Send</span>
            </div>
            <div className="s-step-art" aria-hidden="true">
              <div className="st-send">
                <span className="st-doc">
                  <FileIcon />
                  <span>
                    <b>Letter to Sharma ji</b>
                    <small>Hindi + English · PDF</small>
                  </span>
                </span>
                <span className="st-note">
                  <span className="st-play">
                    <PlayIcon />
                  </span>
                  <span className="st-bars">
                    {Array.from({ length: 16 }, (_, i) => (
                      <i key={i} style={{ height: `${42 + ((i * 43) % 58)}%`, animationDelay: `${(i % 5) * 110}ms` }} />
                    ))}
                  </span>
                  <small>0:21</small>
                </span>
                <span className="st-wa">
                  <CheckIcon /> Ready for WhatsApp · she presses Send
                </span>
              </div>
            </div>
            <h3>She presses Send</h3>
            <p>A polite voice note in Hinglish and a letter with the source for every number. Nothing goes without her.</p>
          </li>
        </ol>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ what Baaki can do
/** `photos`: which "can do" photo slots exist (checked on the server by app/page.tsx). */
export function Features({ photos = [] }: { photos?: string[] }) {
  return (
    <section id="features" className="s-section" aria-labelledby="features-title">
      <div className="s-wrap">
        <header className="s-head">
          <h2 id="features-title" className="s-h2">
            What Baaki <em>can do</em>
          </h2>
          <p className="s-sub">If she can say it, Baaki can work it out and ask for it.</p>
        </header>
        <CanDo photos={photos} />
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ every side of the conversation
function WinDots() {
  return (
    <span className="iw-dots" aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}

export function Interfaces({ art }: { art?: string[] }) {
  const cast = art?.includes("cast-trio");
  return (
    <section id="interfaces" className="s-section" aria-labelledby="interfaces-title">
      <div className="s-wrap">
        <header className={cast ? "s-head s-head-split" : "s-head"}>
          <div className="s-head-text">
            <h2 id="interfaces-title" className="s-h2">
              One Baaki, <em className="s-em-block">every side of the conversation</em>
            </h2>
            <p className="s-sub">
              Lakshmi talks to Baaki in Telugu. Sharma ji hears it in Hinglish. The letter travels on WhatsApp, from her own phone.
            </p>
          </div>
          {cast ? (
            <div className="s-cast">
              <Art name="cast-trio" art={art} w={1120} h={900} className="s-cast-art" />
              <span className="s-cast-names" aria-hidden="true">
                <span>Lakshmi</span>
                <span>Sharma ji</span>
                <span>Mehta madam</span>
              </span>
            </div>
          ) : null}
        </header>
        <ul className="iw-grid">
          {/* worker app */}
          <li className="iw">
            <div className="iw-win" aria-hidden="true">
              <div className="iw-bar">
                <WinDots />
                <span className="iw-url">Baaki · తెలుగు</span>
              </div>
              <div className="iw-body iw-app">
                <p className="iw-app-k" lang="te">
                  రావాల్సిన బాకీ
                </p>
                <p className="iw-app-v">₹12,692</p>
                <ul className="iw-homes">
                  <li>
                    <span className="iw-home">
                      <span lang="te">శర్మ గారు</span>
                      <em className="iw-st iw-st-ready" lang="te">
                        పంపడానికి సిద్ధం
                      </em>
                    </span>
                    <b>₹12,692</b>
                  </li>
                  <li>
                    <span className="iw-home">
                      <span lang="te">రెడ్డి గారు</span>
                      <em className="iw-st iw-st-paid">Fair employer</em>
                    </span>
                    <b>Paid</b>
                  </li>
                  <li>
                    <span className="iw-home">
                      <span lang="te">మెహతా మేడమ్</span>
                      <em className="iw-st iw-st-est">estimate</em>
                    </span>
                    <b>~₹1,500/mo</b>
                  </li>
                </ul>
                <span className="iw-btn" lang="te">
                  పంపండి
                </span>
              </div>
            </div>
            <div className="iw-foot">
              <h3>Lakshmi’s app</h3>
              <p>Telugu, voice first. She confirms every fact.</p>
            </div>
          </li>
          {/* employer page */}
          <li className="iw">
            <div className="iw-win" aria-hidden="true">
              <div className="iw-bar">
                <WinDots />
                <span className="iw-url iw-url-box">/e/ · Sharma ji’s link</span>
              </div>
              <div className="iw-body iw-emp">
                <p className="iw-emp-t" lang="hi">
                  लक्ष्मी का बाकी पैसा
                </p>
                <span className="iw-note">
                  <span className="iw-play">
                    <PlayIcon />
                  </span>
                  <span lang="hi">Voice note सुनिए</span>
                  <small>0:21</small>
                </span>
                <p className="iw-ai" lang="hi">
                  यह voice note Baaki ऐप ने काम करने वाली की अनुमति से बनाया है।
                </p>
                <dl className="iw-items">
                  <div>
                    <dt>Aug – Oct wages</dt>
                    <dd>₹12,000</dd>
                  </div>
                  <div>
                    <dt>Cut over the allowed ₹308</dt>
                    <dd>₹692</dd>
                  </div>
                  <div className="iw-items-total">
                    <dt lang="hi">कुल</dt>
                    <dd>₹12,692</dd>
                  </div>
                </dl>
                <span className="iw-btn" lang="hi">
                  अभी pay करें (UPI)
                </span>
              </div>
            </div>
            <div className="iw-foot">
              <h3>Sharma ji’s page</h3>
              <p>Hinglish. Plays the note, lists every item, opens UPI.</p>
            </div>
          </li>
          {/* WhatsApp share */}
          <li className="iw">
            <div className="iw-win" aria-hidden="true">
              <div className="iw-bar">
                <WinDots />
                <span className="iw-url">Chat · Sharma ji</span>
              </div>
              <div className="iw-body iw-chat">
                <span className="iw-day">Today</span>
                <span className="iw-msg iw-msg-doc">
                  <FileIcon />
                  <span>
                    <b>Baaki letter · Lakshmi</b>
                    <small>Hindi + English · PDF</small>
                  </span>
                </span>
                <span className="iw-msg iw-msg-voice">
                  <span className="iw-play">
                    <PlayIcon />
                  </span>
                  <span className="iw-bars">
                    {Array.from({ length: 18 }, (_, i) => (
                      <i key={i} style={{ height: `${42 + ((i * 29) % 58)}%` }} />
                    ))}
                  </span>
                  <small>0:21</small>
                </span>
                <span className="iw-msg iw-msg-text">
                  Details and UPI: <u>/e/ link</u>
                  <small className="iw-ticks">
                    <CheckIcon />
                  </small>
                </span>
                <span className="iw-shared">Shared from Lakshmi’s own number</span>
              </div>
            </div>
            <div className="iw-foot">
              <h3>WhatsApp</h3>
              <p>She forwards it herself. Baaki never calls anyone.</p>
            </div>
          </li>
        </ul>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ proof band + fair pay teaser
export function ProofBand({ art }: { art?: string[] }) {
  return (
    <section id="proof" className="s-section" aria-labelledby="proof-title">
      <div className="s-wrap s-proof">
        <div id="outcomes" className="s-proof-main">
          <p className="s-micro">Noise proof · Gnani Prisma</p>
          <h2 id="proof-title" className="s-proof-num">
            34<span>/34</span>
          </h2>
          <p className="s-proof-lead">
            rupee amounts heard <em>exactly</em>, in 24 noisy clips of Telugu and Hinglish.
          </p>
          <p className="s-proof-sub">17 of 17 with kitchen noise, a phone line and WhatsApp compression all at once. A small test, run once, with every clip playable.</p>
          <Link href="/proof" className="s-pill s-pill-ink">
            <span>Hear every clip</span>
            <ArrowRightIcon />
          </Link>
          <div className="s-proof-strip">
            <ul className="s-proof-bars" aria-hidden="true">
              {Array.from({ length: 34 }, (_, i) => (
                <li key={i} style={{ animationDelay: `${i * 30}ms` }} />
              ))}
            </ul>
            <span className="s-proof-cap">One bar per rupee amount. All 34 heard exactly.</span>
          </div>
        </div>
        <div className="s-fair">
          <p className="s-micro">For employers</p>
          <h2 className="s-fair-title">
            Am I paying my house help <em>fairly?</em>
          </h2>
          <p>
            Hyderabad’s minimum for a full-time house help is <b>₹16,000 a month</b> (G.O.Ms.No.6, from 1 June 2026). Part-time, that is
            about <b>₹77 an hour</b> <span className="s-est">our estimate</span>.
          </p>
          <dl className="s-fair-table">
            <div>
              <dt>Full-time house help</dt>
              <dd>₹16,000 / month</dd>
            </div>
            <div>
              <dt>2 hours a day</dt>
              <dd>
                about ₹4,000 / month <span className="s-est">estimate</span>
              </dd>
            </div>
            <div>
              <dt>Paying ₹2,500 for 2 hours?</dt>
              <dd>~₹1,500 short every month</dd>
            </div>
          </dl>
          <div className="s-fair-foot">
            <div className="s-fair-actions">
              <Link href={FAIR_CHECK_HREF} className="s-pill s-pill-white">
                <span>Check in 30 seconds</span>
                <ArrowRightIcon />
              </Link>
              <p className="s-fair-links">
                <Link href="/try/employer" className="s-more">
                  Try being Sharma{" "}ji{" "}<span aria-hidden="true">→</span>
                </Link>
                <Link href="/quiz" className="s-more">
                  Fair or Not? Take the 40-second{" "}quiz{" "}<span aria-hidden="true">→</span>
                </Link>
              </p>
            </div>
            <Art name="check-payday-envelope" art={art} w={1300} h={991} className="s-fair-art" />
          </div>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ trust
const TRUST: { icon: ReactNode; tone: string; title: string; body: ReactNode }[] = [
  {
    icon: <CheckIcon />,
    tone: "sage",
    title: "Read back, then she presses Send",
    body: "Every fact is read back and confirmed, and she presses Send herself, every time. Baaki never calls anyone.",
  },
  {
    icon: <BotIcon />,
    tone: "lilac",
    title: "Every AI voice says it is AI",
    body: "Each voice note opens with a disclosure that Baaki made it, in her voice, with her permission.",
  },
  {
    icon: <ShieldIcon />,
    tone: "rose",
    title: "Safety comes first",
    body: (
      <>
        Locked in, hurt, ID taken, a child working: Baaki stops and shows <a href="tel:181">181</a>, <a href="tel:112">112</a> and{" "}
        <a href="tel:1098">1098</a>. Quick exit switches to a plain recipe page.
      </>
    ),
  },
  {
    icon: <FileIcon />,
    tone: "butter",
    title: "Not a lawyer",
    body: "Baaki shows the calculation and where each number comes from, then hands over to legal aid or the labour office. Not legal advice.",
  },
  {
    icon: <LockIcon />,
    tone: "sky",
    title: "Private by design",
    body: "Quick exit also clears this phone’s session. The demo uses only fictional names and amounts.",
  },
];

export function Trust() {
  return (
    <section id="trust" className="s-section" aria-labelledby="trust-title">
      <div className="s-wrap">
        <header className="s-head">
          <h2 id="trust-title" className="s-h2">
            Built for the person <em>with the least power</em> in the room
          </h2>
        </header>
        <ul className="s-trust">
          {TRUST.map((t) => (
            <li key={t.title} className="s-trust-card">
              <span className="s-trust-icon" data-tone={t.tone}>
                {t.icon}
              </span>
              <h3>{t.title}</h3>
              <p>{t.body}</p>
            </li>
          ))}
          <li className="s-trust-card s-trust-exit">
            <span className="s-trust-icon" data-tone="peach">
              <ArrowRightIcon />
            </span>
            <h3>In danger right now?</h3>
            <p>
              <a href="tel:112">112</a> · <a href="tel:181">181 Women</a> · <a href="tel:1098">1098 Child</a>
            </p>
            <Link href="/safety" className="s-textlink">
              Get help →
            </Link>
          </li>
        </ul>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ FAQ
const FAQ: { q: string; a: ReactNode }[] = [
  { q: "Does Baaki contact the employer by itself?", a: "No. Baaki prepares the voice note and the letter. She hears it, checks it and presses Send herself, from her own phone." },
  {
    q: "Where do the amounts come from?",
    a: "From plain rules, never guessed by an AI: Telangana’s minimum wage (G.O.Ms.No.6, 2026) and the Code on Wages, 2019. Every figure shows its source; part-time figures are marked as estimates.",
  },
  { q: "Which languages?", a: "She can speak Telugu, Hindi or a mix. The employer hears the note in their own language: Telugu, Hindi or Hinglish." },
  { q: "Is it free? Does it need an app store?", a: "Free. It runs in the phone’s browser and can be added to the home screen like an app." },
  { q: "Is this legal advice?", a: "No. Baaki shows the calculation and its source, then points to free legal aid or the labour department for the next step." },
];

export function Faq() {
  return (
    <section className="s-section" aria-labelledby="faq-title">
      <div className="s-wrap s-faq">
        <h2 id="faq-title" className="s-h2 s-faq-title">
          Questions, <em>answered</em>
        </h2>
        <div className="s-faq-list">
          {FAQ.map((f) => (
            <details key={f.q} className="s-faq-item">
              <summary>
                <span>{f.q}</span>
                <span className="s-faq-plus" aria-hidden="true" />
              </summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ final CTA + footer
export function FinalCta({ art }: { art?: string[] }) {
  return (
    <section className="s-section s-final-sec" aria-labelledby="cta-title">
      <div className="s-wrap">
        <div className="s-final">
          {/* she speaks (left), she is paid (right): both rise from the card's bottom edge */}
          <Art name="ill-speak" art={art} w={900} h={887} className="s-final-art s-final-art-l" />
          <Art name="ill-celebrate" art={art} w={900} h={850} className="s-final-art s-final-art-r" />
          <LogoMark size={56} />
          <h2 id="cta-title" className="s-final-title">
            Bolo. <em>Baaki sambhal lega.</em>
          </h2>
          <p className="s-final-en">Just speak. Baaki asks.</p>
          <div className="s-hero-ctas">
            <Link href="/app" className="s-pill s-pill-ink s-pill-lg">
              <MicIcon />
              <span>Open Baaki</span>
            </Link>
            <InstallCta label="Install on your phone" className="s-pill-lg" />
          </div>
          <p className="s-final-fine">Free, and runs in the phone’s browser. Add it to the home screen like an app.</p>
        </div>
      </div>
    </section>
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
          <p className="s-footer-h">Baaki</p>
          <Link href="/app">Open the app</Link>
          <Link href="/#how">How it works</Link>
          <Link href="/proof">Noise proof</Link>
        </nav>
        <nav aria-label="More">
          <p className="s-footer-h">More</p>
          <Link href={FAIR_CHECK_HREF}>Fair Pay Check</Link>
          <Link href="/dues">Who owes her</Link>
          <Link href="/safety">Get help</Link>
        </nav>
        <div className="s-footer-help">
          <p className="s-footer-h">In danger right now?</p>
          <p>
            <a href="tel:112">112</a> · <a href="tel:181">181 Women</a> · <a href="tel:1098">1098 Child</a>
          </p>
        </div>
      </div>
      <div className="s-wrap s-footer-base">
        <p>Made for the Gnani.ai Great Indian AI Internship Challenge, 2026. Baaki is not a lawyer and this is not legal advice.</p>
      </div>
      <p className="s-footer-word" aria-hidden="true">
        Baaki
      </p>
    </footer>
  );
}
