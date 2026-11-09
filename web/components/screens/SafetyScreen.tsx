"use client";

// Safety (/safety): a quick exit to a neutral recipe page that is always the first thing on screen (and sticks
// to the top while scrolling), then big tap-to-call helplines. Works with no backend at all (the helplines are
// bundled).

import { useSafety, useT } from "@/hooks";
import type { UiLang } from "@/lib/i18n";
import { ArrowRightIcon, PhoneIcon, ShieldIcon } from "@/components/ui/icons";
import { Screen } from "@/components/ui/primitives";

// Screen-only headline (the body, helplines and buttons come from the shared i18n keys).
const SX: Record<UiLang, { h1: string; em: string }> = {
  en: { h1: "You are", em: "not alone" },
  te: { h1: "మీరు", em: "ఒంటరి కాదు" },
  "hi-en": { h1: "Aap", em: "akeli nahi hain" },
};

export function SafetyScreen() {
  const { t, lang } = useT();
  const s = useSafety();
  const L = SX[lang] ?? SX.en;

  return (
    <Screen title={t("safety.title")} back="/app" t={t} safetyLink={false} className="fx safety-fx">
      <button type="button" className="quick-exit" onClick={s.quickExit}>
        <span>{t("safety.exit")}</span>
        <ArrowRightIcon />
      </button>

      <section className="fx-panel sx-hero" data-wash="rose">
        <div style={{ display: "grid", gap: 8 }}>
          <h2 className="fx-h fx-wash-ink" lang={lang === "te" ? "te" : undefined}>
            {L.h1} <em>{L.em}</em>
          </h2>
          <p className="fx-sub">{t("safety.body")}</p>
        </div>
        <span className="sx-shield" aria-hidden="true">
          <ShieldIcon />
        </span>
        {s.categories.length ? (
          <ul className="sx-cats">
            {s.categories.map((c) => (
              <li key={c.key} className="fx-chip" data-wash="rose">
                {c.label}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section aria-label={t("safety.helplines")}>
        <h2 className="section-title">{t("safety.helplines")}</h2>
        <ul className="sx-lines">
          {s.callable.map((h) => (
            <li key={h.number}>
              <a href={h.href} className="sx-line">
                <span>
                  <span className="sx-num">{h.number}</span>
                  <span className="sx-name">{h.name}</span>
                </span>
                <span className="sx-call">
                  <PhoneIcon />
                  <span>{t("safety.call")}</span>
                </span>
              </a>
            </li>
          ))}
          {s.links.map((h) => (
            <li key={h.name}>
              <a href={h.url} className="sx-line sx-link" target="_blank" rel="noreferrer">
                <span className="sx-name">{h.name}</span>
                <ArrowRightIcon />
              </a>
            </li>
          ))}
        </ul>
      </section>
    </Screen>
  );
}
