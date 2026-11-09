"use client";

// Safety (/safety): big tap-to-call helplines and a quick exit to a neutral recipe page.
// Works with no backend at all (the helplines are bundled).

import { useSafety, useT } from "@/hooks";
import { PhoneIcon } from "@/components/ui/icons";
import { Screen } from "@/components/ui/primitives";

export function SafetyScreen() {
  const { t } = useT();
  const s = useSafety();

  return (
    <Screen title={t("safety.title")} back="/" t={t} safetyLink={false} className="safety-screen">
      <button type="button" className="quick-exit" onClick={s.quickExit}>
        {t("safety.exit")}
      </button>

      <p className="safety-body">{t("safety.body")}</p>
      {s.categories.length ? (
        <ul className="plain-list">
          {s.categories.map((c) => (
            <li key={c.key}>{c.label}</li>
          ))}
        </ul>
      ) : null}

      <section aria-label={t("safety.helplines")}>
        <h2 className="section-title">{t("safety.helplines")}</h2>
        <ul className="helplines">
          {s.callable.map((h) => (
            <li key={h.number}>
              <a href={h.href} className="helpline">
                <PhoneIcon />
                <span className="helpline-number">{h.number}</span>
                <span className="helpline-name">{h.name}</span>
              </a>
            </li>
          ))}
          {s.links.map((h) => (
            <li key={h.name}>
              <a href={h.url} className="helpline helpline-link" target="_blank" rel="noreferrer">
                <span className="helpline-name">{h.name}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </Screen>
  );
}
