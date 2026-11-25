"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Faq = { id: number; question: string; answer: string };

export function PublicFaqList({ fallback }: { fallback: Array<[string, string]> }) {
  const [entries, setEntries] = useState<Faq[]>(fallback.map(([question, answer], index) => ({ id: -(index + 1), question, answer })));
  useEffect(() => {
    let active = true;
    void apiFetch<{ managed: boolean; entries: Faq[] }>("/v1/site-content/public/faqs/")
      .then((content) => { if (active && content.managed) setEntries(content.entries); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);
  if (!entries.length) return <p className="py-8 text-sm text-slate-600">Aucune réponse publiée pour le moment.</p>;
  return <div className="divide-y divide-slate-200 border-y border-slate-200">{entries.map(({ id, question, answer }) => <details key={id} className="faq-item"><summary>{question}</summary><p>{answer}</p></details>)}</div>;
}
