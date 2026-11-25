"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { AddToCartButton } from "@/components/ClientSpace";
import { PublicPromotionStrip } from "@/components/PublicPromotions";
import { availabilityLabel, catalogDetailHref, formatMarketplaceDate, formatMGA, type CatalogProduct, type MarketplaceType, marketplaceTypes } from "@/lib/marketplace.mjs";
import { COUPON_NOTICE, PROMOTION_NOTICE, promotionBadge, promotionConditions, promotionDiscount, promotionPrice } from "@/lib/promotions.mjs";

type CatalogResponse = { count: number; next: string | null; previous: string | null; results: CatalogProduct[] };
type FilterValues = { q: string; city: string; country: string; min_price: string; max_price: string };
type Country = { id: number; name_fr: string };
const emptyFilters: FilterValues = { q: "", city: "", country: "", min_price: "", max_price: "" };
const fieldClass = "mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-500 focus:border-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-100";

function catalogPath(type: MarketplaceType) {
  return type === "medicine" ? "/v1/marketplace/public/medicines/" : "/v1/marketplace/public/equipment/";
}

function queryString(filters: FilterValues, page = 1) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value.trim()) params.set(key, value.trim());
  if (page > 1) params.set("page", String(page));
  return params.toString();
}

export function MarketplaceHomeSection() {
  return <>
    <section className="bg-white px-5 py-14 sm:px-8 sm:py-18"><div className="mx-auto max-w-7xl"><div className="section-heading"><div><p className="section-kicker">Catalogue FANAFODIKO</p><h2 className="section-title">Médicaments et matériel médical</h2></div><p className="section-intro">Consultez les informations, prix et disponibilités publiés par des vendeurs vérifiés. Aucun achat ni service de délivrance en ligne n’est proposé.</p></div><div className="mt-7 grid gap-4 sm:grid-cols-2">{marketplaceTypes.map((category) => <Link key={category.id} href={category.href} className="marketplace-category-card"><span className="marketplace-category-mark" aria-hidden="true">{category.id === "medicine" ? "＋" : "⌕"}</span><span><strong>{category.title}</strong><span>{category.description}</span></span><span className="marketplace-category-arrow" aria-hidden="true">→</span></Link>)}</div><MarketplaceSearchForm className="mt-7" /></div></section>
    <PublicPromotionStrip />
  </>;
}

export function MarketplaceSearchForm({ className = "" }: { className?: string }) {
  return <form action="/recherche" method="get" className={`marketplace-search-form ${className}`}><label className="sr-only" htmlFor="marketplace-search-home">Rechercher dans le catalogue</label><input id="marketplace-search-home" name="q" type="search" maxLength={120} placeholder="Rechercher un médicament ou du matériel médical" className={fieldClass}/><button type="submit" className="rounded-xl bg-blue-800 px-5 py-3 text-sm font-bold text-white hover:bg-blue-900">Rechercher</button></form>;
}

export function ProductCatalog({ productType }: { productType: MarketplaceType }) {
  const category = marketplaceTypes.find(({ id }) => id === productType)!;
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [filters, setFilters] = useState<FilterValues>(emptyFilters);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (nextPage: number, nextFilters: FilterValues) => {
    setLoading(true); setError("");
    const query = queryString(nextFilters, nextPage);
    try {
      const response = await apiFetch<CatalogResponse>(`${catalogPath(productType)}${query ? `?${query}` : ""}`);
      setProducts(response.results); setCount(response.count); setHasNext(Boolean(response.next)); setHasPrevious(Boolean(response.previous)); setPage(nextPage);
    } catch (caught) {
      setProducts([]); setCount(0);
      setError(caught instanceof ApiError ? caught.message : "Le catalogue n’a pas pu être chargé. Vérifiez votre connexion et réessayez.");
    } finally { setLoading(false); }
  }, [productType]);

  useEffect(() => {
    void apiFetch<Country[]>("/v1/reference/countries/").then(setCountries).catch(() => undefined);
    void load(1, emptyFilters);
  }, [load]);

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = Object.fromEntries(Object.keys(emptyFilters).map((key) => [key, String(form.get(key) ?? "")])) as FilterValues;
    setFilters(next); void load(1, next);
  }

  return <><main className="min-h-[65vh] bg-[#f4f9fc] px-5 py-10 sm:px-8 sm:py-14"><div className="mx-auto max-w-7xl"><header className="max-w-3xl"><p className="section-kicker">Marketplace FANAFODIKO</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{category.title}</h1><p className="mt-3 text-sm leading-6 text-slate-600">{category.description}</p>{productType === "medicine" && <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">Les fiches publiées permettent une réservation sans paiement en ligne. Toute prescription doit être suivie auprès d’un professionnel habilité ; la délivrance et le règlement se font auprès de la pharmacie partenaire.</p>}</header>
    <form onSubmit={submitFilters} className="marketplace-filter-panel mt-7" aria-label={`Filtres du catalogue ${category.title.toLocaleLowerCase("fr-FR")}`}>
      <label>Recherche<input name="q" type="search" maxLength={120} defaultValue={filters.q} placeholder="Nom, marque ou principe actif" className={fieldClass}/></label>
      <label>Ville<input name="city" maxLength={120} defaultValue={filters.city} placeholder="Ex. Antananarivo" className={fieldClass}/></label>
      <label>Pays<select name="country" defaultValue={filters.country} className={fieldClass}><option value="">Tous les pays</option>{countries.map((country) => <option key={country.id} value={country.id}>{country.name_fr}</option>)}</select></label>
      <label>Prix minimum (Ar)<input name="min_price" type="number" min="0" step="1" defaultValue={filters.min_price} className={fieldClass}/></label>
      <label>Prix maximum (Ar)<input name="max_price" type="number" min="0" step="1" defaultValue={filters.max_price} className={fieldClass}/></label>
      <button type="submit" className="self-end rounded-xl bg-blue-800 px-5 py-3 text-sm font-bold text-white hover:bg-blue-900">Appliquer</button>
    </form>
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3"><p role="status" className="text-sm font-medium text-slate-600">{loading ? "Chargement du catalogue…" : `${count} fiche${count > 1 ? "s" : ""} publiée${count > 1 ? "s" : ""}`}</p><Link href="/recherche" className="text-sm font-semibold text-blue-800 hover:text-teal-800">Recherche globale →</Link></div>
    {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {!loading && !error && products.length === 0 && <div className="marketplace-empty mt-5"><span className="marketplace-empty-icon" aria-hidden="true">＋</span><h2>Aucune fiche publiée pour le moment</h2><p>Les fiches apparaîtront ici après vérification des informations du produit et du vendeur.</p></div>}
    {products.length > 0 && <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{products.map((product) => <ProductCard key={product.id} product={product}/>)}</div>}
    <div className="mt-7 flex justify-between"><button type="button" disabled={!hasPrevious || loading} onClick={() => void load(page - 1, filters)} className="marketplace-page-button">← Précédent</button><button type="button" disabled={!hasNext || loading} onClick={() => void load(page + 1, filters)} className="marketplace-page-button">Suivant →</button></div>
  </div></main><PublicPromotionStrip /></>;
}

function useUnusableProductImage(src: string | null | undefined) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const fail = useCallback(() => setUnavailable(true), []);

  useEffect(() => {
    setUnavailable(false);
  }, [src]);

  useEffect(() => {
    const image = imageRef.current;
    if (!image || !src) return;
    const check = () => {
      if (image.complete && (image.naturalWidth <= 1 || image.naturalHeight <= 1)) fail();
    };
    if (image.complete) check();
    else {
      image.addEventListener("load", check);
      image.addEventListener("error", fail);
    }
    return () => {
      image.removeEventListener("load", check);
      image.removeEventListener("error", fail);
    };
  }, [src, fail]);

  return { imageRef, unavailable, fail };
}

function ProductCardImage({ product }: { product: CatalogProduct }) {
  const { imageRef, unavailable, fail } = useUnusableProductImage(product.image_url);
  if (!product.image_url || unavailable) {
    return <div className="marketplace-product-image marketplace-image-empty" aria-label="Aucune image exploitable">Image non fournie</div>;
  }
  return <Link href={catalogDetailHref(product)} aria-label={`Voir la fiche ${product.title}`} className="marketplace-product-image"><Image ref={imageRef} src={product.image_url} alt={product.title} width={500} height={320} sizes="(max-width: 639px) 92vw, (max-width: 1023px) 45vw, 350px" unoptimized loading="lazy" onLoad={(event) => {
    if (event.currentTarget.naturalWidth <= 1 || event.currentTarget.naturalHeight <= 1) fail();
  }} onError={fail}/></Link>;
}

export function ProductCard({ product }: { product: CatalogProduct }) {
  const promotion = product.promotion ?? null;
  return <article className="marketplace-product-card"><ProductCardImage product={product} /><div className="flex flex-1 flex-col p-4"><div className="flex flex-wrap gap-2">{promotionBadge(promotion) && <span className="rounded-full bg-emerald-700 px-3 py-1 text-xs font-extrabold text-white">{promotionBadge(promotion)}</span>}{product.is_sponsored && <span className="marketplace-sponsored">Sponsorisé</span>}{product.product_type === "medicine" && <span className="marketplace-neutral-badge">Médicament</span>}</div><h2 className="mt-2 text-lg font-bold leading-snug text-slate-900"><Link href={catalogDetailHref(product)} className="hover:text-blue-800">{product.title}</Link></h2>{product.brand && <p className="mt-1 text-sm text-slate-600">{product.brand}</p>}{product.product_type === "medicine" && <p className="mt-2 text-xs leading-5 text-slate-600">{product.active_ingredient} · {product.dosage} · {product.pharmaceutical_form} · {product.packaging}</p>}{product.product_type === "equipment" && <p className="mt-2 text-xs text-slate-600">{product.equipment_category_label}{product.model_name ? ` · ${product.model_name}` : ""}</p>}<p className="mt-3 text-xl font-extrabold text-blue-900">{formatMGA(promotionPrice(product))}{promotion && <span className="ml-2 rounded-full bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-800">{promotionDiscount(promotion)}</span>}</p>{promotion && <p className="mt-1 text-xs text-slate-500"><span className="line-through">{formatMGA(promotion.original_price_mga)}</span> · {promotionConditions(promotion).join(" · ")}</p>}<p className="mt-1 text-xs font-semibold text-teal-800">{availabilityLabel(product.availability)}</p><p className="mt-3 text-xs leading-5 text-slate-600">{product.seller.name} · {product.seller.city}, {product.seller.country}</p><p className="mt-2 text-[.7rem] leading-5 text-slate-500">Prix mis à jour le {formatMarketplaceDate(product.price_updated_at)} · Disponibilité mise à jour le {formatMarketplaceDate(product.availability_updated_at)}</p>{product.product_type === "medicine" && <p className="mt-2 text-xs font-semibold text-amber-900">{product.requires_prescription ? "Ordonnance nécessaire" : "Prescription non requise selon la fiche vérifiée"}</p>}<Link href={catalogDetailHref(product)} className="mt-4 inline-flex min-h-10 items-center justify-center rounded-lg border border-blue-200 px-3 py-2 text-sm font-bold text-blue-800 hover:bg-blue-50">Consulter la fiche</Link></div></article>;
}

export function GlobalMarketplaceSearch({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [deferredCategories, setDeferredCategories] = useState<string[]>(["pharmacies", "doctors", "specialists", "laboratories"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const search = useCallback(async (term: string) => {
    setQuery(term); setError("");
    if (!term.trim()) { setProducts([]); setLoading(false); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams({ q: term.trim() });
      const response = await apiFetch<{ products: CatalogProduct[]; deferred_categories: string[] }>(`/v1/marketplace/public/search/?${params}`);
      setProducts(response.products); setDeferredCategories(response.deferred_categories);
    } catch (caught) {
      setProducts([]); setError(caught instanceof ApiError ? caught.message : "La recherche n’a pas pu être effectuée.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (initialQuery) void search(initialQuery); }, [initialQuery, search]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = String(new FormData(event.currentTarget).get("q") ?? "");
    window.history.replaceState(null, "", value.trim() ? `/recherche?q=${encodeURIComponent(value.trim())}` : "/recherche");
    void search(value);
  }

  const categoryNames: Record<string, string> = { pharmacies: "Pharmacies", doctors: "Médecins", specialists: "Spécialistes", laboratories: "Laboratoires" };
  return <main className="min-h-[65vh] bg-[#f4f9fc] px-5 py-10 sm:px-8 sm:py-14"><div className="mx-auto max-w-7xl"><p className="section-kicker">Catalogue FANAFODIKO</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Recherche globale</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Recherchez parmi les fiches publiées de médicaments et de matériel médical. Les catégories professionnelles seront accessibles quand un annuaire public fiable sera ouvert.</p><form onSubmit={submit} className="marketplace-search-form mt-6 max-w-3xl"><label className="sr-only" htmlFor="global-marketplace-search">Mots-clés</label><input id="global-marketplace-search" name="q" type="search" maxLength={120} defaultValue={initialQuery} placeholder="Nom, principe actif, marque, modèle…" className={fieldClass}/><button className="rounded-xl bg-blue-800 px-5 py-3 text-sm font-bold text-white hover:bg-blue-900">Rechercher</button></form>
    {query && <p className="mt-5 text-sm font-medium text-slate-600">{loading ? "Recherche…" : `${products.length} résultat${products.length === 1 ? "" : "s"} affiché${products.length === 1 ? "" : "s"} pour « ${query} »`}</p>}{error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {products.length > 0 && <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{products.map((product) => <ProductCard key={product.id} product={product}/>)}</div>}
    {query && !loading && !error && products.length === 0 && <div className="marketplace-empty mt-5"><h2>Aucun produit publié ne correspond à cette recherche</h2><p>Essayez un autre nom ou une autre marque. Aucun produit non vérifié n’est affiché.</p></div>}
    <section className="mt-9 rounded-2xl border border-slate-200 bg-white p-5 sm:p-6"><h2 className="text-lg font-bold text-slate-900">Catégories professionnelles</h2><p className="mt-2 text-sm leading-6 text-slate-600">L’annuaire public n’est pas encore ouvert. Aucun profil professionnel n’est affiché par cette recherche.</p><ul className="mt-4 flex flex-wrap gap-2">{deferredCategories.map((category) => <li key={category} className="marketplace-neutral-badge">{categoryNames[category] ?? category} · bientôt disponible</li>)}</ul></section>
  </div></main>;
}

export function ProductDetail({ slug, expectedType }: { slug: string; expectedType: MarketplaceType }) {
  const [product, setProduct] = useState<CatalogProduct | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const { imageRef, unavailable, fail } = useUnusableProductImage(product?.image_url);
  useEffect(() => {
    let active = true;
    void apiFetch<CatalogProduct>(`/v1/marketplace/public/products/${encodeURIComponent(slug)}/`)
      .then((item) => { if (active) { setProduct(item.product_type === expectedType ? item : null); setState(item.product_type === expectedType ? "ready" : "empty"); } })
      .catch(() => { if (active) setState("empty"); });
    return () => { active = false; };
  }, [slug, expectedType]);
  if (state === "loading") return <main className="min-h-[60vh] px-5 py-14 text-center text-slate-600">Chargement de la fiche…</main>;
  if (!product || state !== "ready") return <main className="min-h-[60vh] bg-[#f4f9fc] px-5 py-14"><div className="marketplace-empty mx-auto max-w-3xl"><h1>Cette fiche n’est pas disponible</h1><p>Elle n’existe pas ou n’est plus publiée par un vendeur vérifié.</p><Link href={expectedType === "medicine" ? "/medicaments" : "/materiel-medical"} className="mt-4 inline-flex font-bold text-blue-800">Retour au catalogue</Link></div></main>;
  return <main className="min-h-[65vh] bg-[#f4f9fc] px-5 py-10 sm:px-8 sm:py-14"><article className="mx-auto grid max-w-6xl gap-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8 lg:grid-cols-[.9fr_1.1fr]">{product.image_url && !unavailable ? <Image ref={imageRef} src={product.image_url} alt={product.title} width={800} height={620} sizes="(max-width: 1023px) 92vw, 45vw" unoptimized className="aspect-[4/3] w-full rounded-2xl object-cover" onLoad={(event) => {
      if (event.currentTarget.naturalWidth <= 1 || event.currentTarget.naturalHeight <= 1) fail();
    }} onError={fail}/> : <div className="marketplace-product-image marketplace-image-empty min-h-64 rounded-2xl" aria-label="Aucune image exploitable">Image non fournie</div>}<div><Link href={expectedType === "medicine" ? "/medicaments" : "/materiel-medical"} className="text-sm font-bold text-blue-800">← Retour au catalogue</Link><div className="mt-4 flex flex-wrap gap-2">{promotionBadge(product.promotion) && <span className="rounded-full bg-emerald-700 px-3 py-1 text-xs font-extrabold text-white">{promotionBadge(product.promotion)}</span>}{product.is_sponsored && <span className="marketplace-sponsored">Sponsorisé</span>}<span className="marketplace-neutral-badge">{product.product_type_label}</span></div><h1 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-950">{product.title}</h1>{product.brand && <p className="mt-2 text-slate-600">{product.brand}</p>}<p className="mt-4 text-3xl font-extrabold text-blue-900">{formatMGA(promotionPrice(product))}{product.promotion && <span className="ml-3 rounded-full bg-emerald-50 px-3 py-1 text-sm font-bold text-emerald-800">{promotionDiscount(product.promotion)}</span>}</p>{product.promotion && <><p className="mt-1 text-sm text-slate-500">Prix initial : <span className="line-through">{formatMGA(product.promotion.original_price_mga)}</span></p><p role="note" className="mt-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-950">{PROMOTION_NOTICE} {COUPON_NOTICE} {promotionConditions(product.promotion).join(" · ")}</p></>}<p className="mt-2 font-semibold text-teal-800">{availabilityLabel(product.availability)}</p><p className="mt-3 text-sm text-slate-600">{product.seller.name} · {product.seller.city}, {product.seller.country} <span className="ml-1 rounded-full bg-teal-50 px-2 py-1 text-xs font-bold text-teal-800">Vendeur vérifié</span></p><p className="mt-5 whitespace-pre-line text-sm leading-6 text-slate-700">{product.description || "Aucune description complémentaire."}</p>
    {product.product_type === "medicine" ? <dl className="mt-6 grid gap-3 rounded-2xl bg-[#f4f9fc] p-4 text-sm sm:grid-cols-2">{[["Principe actif", product.active_ingredient], ["Dosage", product.dosage], ["Forme", product.pharmaceutical_form], ["Conditionnement", product.packaging]].map(([label, value]) => <div key={label}><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 font-semibold text-slate-800">{value}</dd></div>)}</dl> : <section className="mt-6 rounded-2xl bg-[#f4f9fc] p-4"><h2 className="font-bold text-slate-900">Caractéristiques</h2><p className="mt-2 text-sm font-semibold text-slate-700">{product.equipment_category_label}{product.model_name ? ` · ${product.model_name}` : ""}</p>{Object.entries(product.technical_specifications ?? {}).length > 0 && <dl className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(product.technical_specifications).map(([label, value]) => <div key={label} className="text-sm"><dt className="text-xs text-slate-500">{label}</dt><dd className="font-medium text-slate-800">{String(value)}</dd></div>)}</dl>}{product.warranty && <p className="mt-3 text-sm text-slate-700"><strong>Garantie :</strong> {product.warranty}</p>}</section>}
    <div className="mt-5 grid gap-2 border-t border-slate-100 pt-4 text-xs leading-5 text-slate-500"><p>Prix mis à jour le {formatMarketplaceDate(product.price_updated_at)}.</p><p>Disponibilité mise à jour le {formatMarketplaceDate(product.availability_updated_at)}.</p></div>{product.product_type === "medicine" && <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-950">{product.requires_prescription ? "Une ordonnance est nécessaire. Consultez un professionnel habilité." : "Consultez la pharmacie pour toute question sur l’usage de ce produit."} La réservation ne vaut ni paiement ni délivrance ; le retrait et le règlement se font auprès du vendeur partenaire.</p>}<AddToCartButton productId={product.id} requiresPrescription={product.product_type === "medicine" && product.requires_prescription} isOrderable={product.is_orderable} unavailableReason={product.orderability_reason}/></div></article></main>;
}
