"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PublicNavigation } from "@/components/PublicNavigation";
import { apiFetch } from "@/lib/api";

export function PublicPageLayout({ children }: { children: React.ReactNode }) {
  return <><a className="skip-link" href="#contenu">Aller au contenu</a><PublicNavigation /><main id="contenu" className="min-h-[65vh]">{children}</main><footer className="border-t border-slate-200 bg-slate-950 text-slate-300"><div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-8 sm:px-8 md:flex-row md:items-center md:justify-between"><Link href="/" className="text-sm font-extrabold tracking-wide text-white">FANAFODIKO<span className="text-teal-400">.</span></Link><nav aria-label="Liens de pied de page" className="flex flex-wrap gap-x-5 gap-y-2 text-xs"><Link href="/a-propos" className="footer-link">À propos</Link><Link href="/faq" className="footer-link">FAQ</Link><Link href="/contact" className="footer-link">Contact</Link><Link href="/actualites" className="footer-link">Actualités</Link><Link href="/conditions" className="footer-link">Conditions d’utilisation</Link><Link href="/confidentialite" className="footer-link">Confidentialité</Link><Link href="/professionnel" className="footer-link">Espace professionnel</Link></nav><p className="text-xs text-slate-400">© 2026 FANAFODIKO · Votre santé, plus proche.</p></div></footer></>;
}

export function PageHeading({ kicker, title, intro, page }: { kicker: string; title: string; intro: string; page?: "about" | "contact" | "terms" | "privacy" }) {
  const [copy, setCopy] = useState<{ title: string; introduction: string; body: string } | null>(null);
  useEffect(() => {
    if (!page) return;
    let active = true;
    void apiFetch<{ title: string; introduction: string; body: string }>(`/v1/site-content/public/pages/${page}/`)
      .then((content) => { if (active) setCopy(content); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [page]);
  const visibleIntro = copy ? copy.introduction : intro;
  return <header className="bg-gradient-to-br from-blue-50 via-white to-teal-50 px-5 py-14 sm:px-8 sm:py-20"><div className="mx-auto max-w-4xl"><p className="section-kicker">{kicker}</p><h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{copy?.title ?? title}</h1>{visibleIntro && <p className="mt-4 max-w-3xl whitespace-pre-line text-base leading-7 text-slate-600">{visibleIntro}</p>}{copy?.body && <p className="mt-4 max-w-3xl whitespace-pre-line text-sm leading-7 text-slate-600">{copy.body}</p>}</div></header>;
}
