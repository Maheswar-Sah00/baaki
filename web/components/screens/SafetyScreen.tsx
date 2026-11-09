"use client";

// Safety (/safety): big tap-to-call helplines and a quick exit to a neutral recipe page.
// Works with no backend at all (the helplines are bundled).

import { useSafety, useT } from "@/hooks";
import { ArrowRightIcon, PhoneIcon } from "@/components/ui/icons";
import { Illustration, Screen } from "@/components/ui/primitives";

export function SafetyScreen() {
  const { t } = useT();
  const s = useSafety();

  return (
    <Screen title={t("safety.title")} back="/app" t={t} safetyLink={false} className="safety-screen">
      <button type="button" className="quick-exit" onClick={s.quickExit}>
        {t("safety.exit")}
      </button>

      <section className="card safety-hero">
        <Illustration name="shield" size={170} animated className="safety-ill" />
        <p className="safety-body">{t("safety.body")}</p>
        {s.categories.length ? (
          <ul className="safety-cats">
            {s.categories.map((c) => (
              <li key={c.key} className="pill" data-tone="warn">
                {c.label}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section aria-label={t("safety.helplines")}>
        <h2 className="section-title">{t("safety.helplines")}</h2>
        <ul className="helplines">
          {s.callable.map((h) => (
            <li key={h.number}>
              <a href={h.href} className="helpline">
                <span className="helpline-text">
                  <span className="helpline-number">{h.number}</span>
                  <span className="helpline-name">{h.name}</span>
                </span>
                <span className="helpline-call">
                  <PhoneIcon />
                  <span>{t("safety.call")}</span>
                </span>
              </a>
            </li>
          ))}
          {s.links.map((h) => (
            <li key={h.name}>
              <a href={h.url} className="helpline helpline-link" target="_blank" rel="noreferrer">
                <span className="helpline-name">{h.name}</span>
                <ArrowRightIcon />
              </a>
            </li>
          ))}
        </ul>
      </section>
    </Screen>
  );
}
