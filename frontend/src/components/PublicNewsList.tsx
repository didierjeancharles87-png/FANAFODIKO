"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type News = { id: number; title: string; summary: string; body: string; published_at: string | null };

export function PublicNewsList() {
  const [articles, setArticles] = useState<News[]>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    void apiFetch<News[]>("/v1/site-content/public/news/")
      .then((items) => { if (active) setArticles(items); })
      .catch(() => undefined)
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, []);
  if (!loaded) return <p className="mt-7 text-center text-sm text-slate-500" role="status">Chargement des actualités…</p>;
  if (!articles.length) return <div className="mt-7 rounded-3xl border border-dashed border-slate-300 bg-white/70 px-6 py-10 text-center sm:py-12"><span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-xl text-blue-700" aria-hidden="true">✦</span><h2 className="mt-4 font-semibold text-slate-900">Aucune actualité publiée pour le moment</h2><p className="mt-2 text-sm text-slate-500">Les informations officielles seront partagées dans cet espace.</p></div>;
  return <div className="mt-7 grid gap-4 md:grid-cols-2">{articles.map((article) => <article key={article.id} className="info-card"><p className="section-kicker">Actualité</p><h2 className="mt-2 text-lg font-bold text-slate-900">{article.title}</h2>{article.published_at && <time className="mt-1 block text-xs text-slate-500" dateTime={article.published_at}>{new Intl.DateTimeFormat("fr-FR", { dateStyle: "long" }).format(new Date(article.published_at))}</time>}<p className="mt-3 text-sm font-medium leading-6 text-slate-700">{article.summary}</p><p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-600">{article.body}</p></article>)}</div>;
}
