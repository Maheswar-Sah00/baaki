"use client";

// Mount point for the Exit Kit: "I was asked to leave" (dashboard card or CaseScreen).
//   <ExitLink employerId={c.employer?.id} caseId={c.case_id} />

import Link from "next/link";
import { useT } from "@/hooks";
import { exitStrings } from "./strings";

export function ExitLink({
  employerId,
  caseId,
  variant = "button",
}: {
  employerId?: number | null;
  caseId?: number | null;
  variant?: "button" | "text";
}) {
  const { lang } = useT();
  const x = exitStrings(lang);
  const q = new URLSearchParams();
  if (employerId != null) q.set("employer", String(employerId));
  if (caseId != null) q.set("case", String(caseId));
  return (
    <Link href={`/exit?${q}`} className={variant === "button" ? "btn btn-ghost" : "meta"} aria-label={`${x("link")}: ${x("link_hint")}`}>
      {x("link")}
    </Link>
  );
}
