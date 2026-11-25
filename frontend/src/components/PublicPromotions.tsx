"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { formatMGA } from "@/lib/marketplace.mjs";
import { COUPON_NOTICE, PROMOTION_NOTICE, promotionBadge, promotionConditions } from "@/lib/promotions.mjs";
import { PublicNavigation } from "@/components/PublicNavigation";

type PublicPromotion = {
  id: number;
  code: string;
  title: string;
  product: number;
  product_title: string;
  product_slug: string;
  product_type: "medicine" | "equipment";
  image_url: string | null;
  discount_type: string;
  discount_label: string;
  discount_value: string;
  original_price_mga: string;
  promotional_price_mga: string;
  starts_at: string;
  ends_at: string;
  max_redemptions: number | null;
  remaining_quantity: number | null;
};

type PromotionPage = { count: number; next: string | null; previous: string | null; results: PublicPromotion[] };

const promotionHref = (promotion: PublicPromotion) =>
  promotion.product_type === "medicine"
    ? `/medicaments/${encodeURIComponent(promotion.product_slug)}`
    : `/materiel-medical/${encodeURIComponent(promotion.product_slug)}`;

function describeError(caught: unknown, fallback: string) {
  return caught instanceof ApiError ? caught.message : fallback;
}

function PromotionCard({ promotion }: { promotion: PublicPromotion }) {
  const conditions = promotionConditions(promotion);
  return <article className="rounded-2xl border border-emerald-200 bg-white p-4 shadow-sm">
    <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-emerald-700 px-3 py-1 text-xs font-extrabold text-white">{promotionBadge(promotion)}</span><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-900">{promotion.discount_label}</span></div>
    <h3 className="mt-3 font-bold text-slate-950">{promotion.title}</h3>
    <p className="mt-1 text-sm text-slate-600">{promotion.product_title}</p>
    <p className="mt-3"><span className="text-xs text-slate-500 line-through">{formatMGA(promotion.original_price_mga)}</span><br/><span className="text-xl font-extrabold text-emerald-800">{formatMGA(promotion.promotional_price_mga)}</span></p>
    {conditions.length > 0 && <ul className="mt-3 space-y-1 text-xs text-slate-600">{conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>}
    <Link href={promotionHref(promotion)} className="mt-4 inline-flex rounded-xl border border-emerald-300 px-3 py-2 text-sm font-bold text-emerald-800 hover:bg-emerald-50">Voir la fiche →</Link>
  </article>;
}

export function PublicPromotionStrip() {
  const [promotions, setPromotions] = useState<PublicPromotion[]>([]);
  useEffect(() => {
    let active = true;
    void apiFetch<PromotionPage>("/v1/promotions/public/?limit=3")
      .then((data) => { if (active) setPromotions(data.results); })
      .catch(() => { if (active) setPromotions([]); });
    return () => { active = false; };
  }, []);
  if (promotions.length === 0) return null;
  return <section className="border-t border-emerald-100 bg-emerald-50/60 px-5 py-10 sm:px-8" aria-labelledby="public-promotions-heading">
    <div className="mx-auto max-w-7xl"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="section-kicker">Offres vérifiées</p><h2 id="public-promotions-heading" className="section-title">Promotions en cours</h2></div><Link href="/promotions" className="text-sm font-bold text-emerald-800">Toutes les promotions →</Link></div>
      <p role="note" className="mt-3 max-w-3xl text-sm leading-6 text-emerald-950">{PROMOTION_NOTICE} {COUPON_NOTICE}</p>
      <div className="mt-5 grid gap-4 md:grid-cols-3">{promotions.map((promotion) => <PromotionCard key={promotion.id} promotion={promotion}/>)}</div>
    </div>
  </section>;
}

export function PublicPromotionsPage() {
  const [promotions, setPromotions] = useState<PublicPromotion[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true); setError('');
    return apiFetch<PromotionPage>("/v1/promotions/public/?limit=24")
      .then((data) => { setPromotions(data.results); setError(""); })
      .catch((caught) => setError(describeError(caught, "Les promotions n’ont pas pu être chargées.")))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <>
    <PublicNavigation />
    <main className="min-h-screen bg-[#f4f9fc] px-5 py-10 sm:px-8">
      <div className="mx-auto max-w-6xl"><p className="section-kicker">Catalogue FANAFODIKO</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Promotions vérifiées</h1>
        <p role="note" className="mt-3 max-w-4xl rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-950">{PROMOTION_NOTICE} {COUPON_NOTICE}</p>
        {error && <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
        {loading ? <p className="mt-6 text-sm text-slate-600">Chargement des promotions…</p> : promotions.length === 0 ? <p className="mt-6 text-sm text-slate-600">Aucune promotion active n’est publiée pour le moment.</p> : <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{promotions.map((promotion) => <PromotionCard key={promotion.id} promotion={promotion}/>)}</div>}
      </div>
    </main>
  </>;
}
