"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, apiFetch, apiMutate } from "@/lib/api";
import { formatMGA, formatMarketplaceDate } from "@/lib/marketplace.mjs";
import {
  NO_ONLINE_PAYMENT_NOTICE,
  PRESCRIPTION_NOTICE,
  PICKUP_NOTICE,
  RESERVATION_NOTICE,
  canSubmitForReview,
  moderationStatusLabel,
} from "@/lib/phase7.mjs";
import { orderHistoryFromLabel, orderStatusLabel } from "@/lib/status-labels.mjs";
import {
  COUPON_NOTICE,
  PROMOTION_NOTICE,
  canEditPromotion,
  canRequestPromotionRemoval,
  fromDateTimeLocal,
  promotionConditions,
  promotionDiscount,
  promotionStatusLabel,
  toDateTimeLocal,
} from "@/lib/promotions.mjs";
import { PublicNavigation } from "@/components/PublicNavigation";

type PartnerProduct = {
  id: number;
  product_type: "medicine" | "equipment";
  product_type_label: string;
  title: string;
  slug: string;
  brand: string;
  description: string;
  status: string;
  moderation_status: string;
  moderation_status_label: string;
  review_notes: string;
  price_mga: string;
  availability: string;
  stock_quantity: number | null;
  stock_updated_at: string | null;
  active_ingredient: string;
  dosage: string;
  pharmaceutical_form: string;
  packaging: string;
  requires_prescription: boolean;
  authorization_status: string;
  authorization_status_label: string;
  authorization_reference: string;
  authorization_verified_reference: string;
  authorization_review_notes: string;
  authorization_reviewed_at: string | null;
  authorization_decision_tracked: boolean;
  equipment_category: string;
  model_name: string;
  technical_specifications: Record<string, string | number | boolean>;
  warranty: string;
};

type OrderItem = {
  id: number;
  title: string;
  unit_price_mga: string;
  quantity: number;
  line_total_mga: string;
  requires_prescription: boolean;
  prescription_checked_by_seller: boolean;
};

type OrderEvent = { id: number; from_status: string; to_status: string; note: string; created_at: string };

type PartnerOrder = {
  id: number;
  reference: string;
  status: string;
  total_mga: string;
  customer_note: string;
  rejection_reason: string;
  created_at: string;
  items: OrderItem[];
  events: OrderEvent[];
};

type PartnerImage = {
  id: number;
  file_url: string;
  alt_text: string;
  sort_order: number;
  is_primary: boolean;
};

type Page<T> = { count: number; results: T[] };

type PartnerPromotion = {
  id: number;
  code: string;
  title: string;
  seller: number;
  seller_name: string;
  product: number;
  product_title: string;
  product_slug: string;
  discount_type: string;
  discount_type_label: string;
  discount_value: string;
  discount_label: string;
  original_price_mga: string;
  promotional_price_mga: string;
  starts_at: string;
  ends_at: string;
  max_redemptions: number | null;
  redemption_count: number;
  remaining_quantity: number | null;
  status: string;
  status_label: string;
  review_notes: string;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

type PromotionResult = {
  code: string;
  title: string;
  status: string;
  redemption_count: number;
  quantity_used: number;
  total_discount_mga: string;
  remaining_quantity: number | null;
};

type Dashboard = {
  seller_id: number;
  products: Record<string, number>;
  orders: Record<string, number>;
  unread_notifications: number;
};

const box = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
const field = "mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900";
const primaryButton = "rounded-xl bg-blue-800 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-900 disabled:opacity-60";
const secondaryButton = "rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60";
const noticeClass = "rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950";

function describeError(caught: unknown, fallback: string) {
  if (caught instanceof ApiError) {
    return caught.details ? `${caught.message} ${JSON.stringify(caught.details)}` : caught.message;
  }
  return fallback;
}

function productPayload(form: FormData, productType: "medicine" | "equipment") {
  const stock = String(form.get("stock_quantity") ?? "").trim();
  const payload: Record<string, string | number | boolean | null | Record<string, string | number | boolean>> = {
    product_type: productType,
    title: String(form.get("title") ?? ""),
    brand: String(form.get("brand") ?? ""),
    description: String(form.get("description") ?? ""),
    price_mga: String(form.get("price_mga") ?? ""),
    availability: String(form.get("availability") ?? "unavailable"),
    stock_quantity: stock === "" ? null : Number(stock),
  };
  if (productType === "medicine") {
    Object.assign(payload, {
      active_ingredient: String(form.get("active_ingredient") ?? ""),
      dosage: String(form.get("dosage") ?? ""),
      pharmaceutical_form: String(form.get("pharmaceutical_form") ?? ""),
      packaging: String(form.get("packaging") ?? ""),
      requires_prescription: form.get("requires_prescription") === "on",
      authorization_reference: String(form.get("authorization_reference") ?? ""),
    });
  } else {
    let specifications: Record<string, string | number | boolean> = {};
    try {
      const parsed: unknown = JSON.parse(String(form.get("technical_specifications") ?? "{}"));
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        specifications = parsed as Record<string, string | number | boolean>;
      }
    } catch {
      throw new Error("Les caractéristiques techniques doivent être un objet JSON valide.");
    }
    Object.assign(payload, {
      equipment_category: String(form.get("equipment_category") ?? ""),
      model_name: String(form.get("model_name") ?? ""),
      technical_specifications: specifications,
      warranty: String(form.get("warranty") ?? ""),
    });
  }
  return payload;
}

function ProductFields({ productType, product }: { productType: "medicine" | "equipment"; product?: PartnerProduct | null }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block text-sm font-semibold">Titre<input name="title" required maxLength={180} defaultValue={product?.title ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Marque ou laboratoire<input name="brand" maxLength={160} defaultValue={product?.brand ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Prix en Ariary<input name="price_mga" type="number" min="0.01" step="0.01" required defaultValue={product?.price_mga ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Stock réel (laisser vide si inconnu)<input name="stock_quantity" type="number" min="0" step="1" defaultValue={product?.stock_quantity ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Disponibilité déclarée<select name="availability" defaultValue={product?.availability ?? "unavailable"} className={field}>
        <option value="available">Disponible</option><option value="limited">Disponibilité limitée</option><option value="unavailable">Indisponible</option>
      </select></label>
      <label className="block text-sm font-semibold sm:col-span-2">Description<textarea name="description" rows={3} maxLength={4000} defaultValue={product?.description ?? ""} className={field}/></label>
      {productType === "medicine" ? <>
        <label className="block text-sm font-semibold">Principe actif<input name="active_ingredient" required maxLength={180} defaultValue={product?.active_ingredient ?? ""} className={field}/></label>
        <label className="block text-sm font-semibold">Dosage<input name="dosage" required maxLength={120} defaultValue={product?.dosage ?? ""} className={field}/></label>
        <label className="block text-sm font-semibold">Forme pharmaceutique<input name="pharmaceutical_form" required maxLength={120} defaultValue={product?.pharmaceutical_form ?? ""} className={field}/></label>
        <label className="block text-sm font-semibold">Conditionnement<input name="packaging" required maxLength={160} defaultValue={product?.packaging ?? ""} className={field}/></label>
        <p className="col-span-full rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">Vous déclarez uniquement la référence AMM. Le statut est décidé par l’administration ; modifier la référence remet la fiche en attente de vérification.</p>
        {product && <p className="col-span-full text-xs text-slate-600">Statut AMM : <strong>{product.authorization_status_label || product.authorization_status}</strong>{product.authorization_verified_reference ? ` · référence vérifiée : ${product.authorization_verified_reference}` : ""}{product.authorization_review_notes ? ` · motif : ${product.authorization_review_notes}` : ""}</p>}
        <label className="block text-sm font-semibold">Référence AMM<input name="authorization_reference" maxLength={160} defaultValue={product?.authorization_reference ?? ""} className={field}/></label>
        <label className="col-span-full flex items-center gap-2 text-sm font-semibold"><input name="requires_prescription" type="checkbox" defaultChecked={product?.requires_prescription ?? true}/>Ordonnance nécessaire</label>
      </> : <>
        <label className="block text-sm font-semibold">Catégorie<select name="equipment_category" required defaultValue={product?.equipment_category ?? ""} className={field}>
          <option value="">Choisir</option><option value="diagnostic">Diagnostic</option><option value="monitoring">Surveillance médicale</option>
          <option value="mobility">Mobilité et transfert</option><option value="protection">Protection</option>
          <option value="consumables">Consommables</option><option value="other">Autre matériel médical</option>
        </select></label>
        <label className="block text-sm font-semibold">Modèle<input name="model_name" maxLength={160} defaultValue={product?.model_name ?? ""} className={field}/></label>
        <label className="block text-sm font-semibold sm:col-span-2">Caractéristiques (objet JSON)<textarea name="technical_specifications" rows={3} defaultValue={JSON.stringify(product?.technical_specifications ?? {})} className={field}/></label>
        <label className="block text-sm font-semibold sm:col-span-2">Garantie<input name="warranty" maxLength={240} defaultValue={product?.warranty ?? ""} className={field}/></label>
      </>}
    </div>
  );
}

export function PartnerPageShell({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  const links = [
    ["/partenaire", "Tableau de bord"],
    ["/partenaire/produits", "Produits"],
    ["/partenaire/images", "Images"],
    ["/partenaire/promotions", "Promotions"],
    ["/partenaire/commandes", "Commandes"],
  ] as const;
  return <>
    <PublicNavigation />
    <main className="min-h-screen bg-[#f4f9fc] px-5 py-10 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-bold uppercase tracking-wide text-teal-700">Espace partenaire</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">{title}</h1>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">{intro}</p>
        <nav aria-label="Navigation partenaire" className="mt-5 flex flex-wrap gap-2 border-b border-slate-200 pb-5">
          {links.map(([href, label]) => <Link key={href} href={href} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-teal-500 hover:text-teal-800">{label}</Link>)}
        </nav>
        <div className="mt-6 space-y-5">{children}</div>
      </div>
    </main>
  </>;
}

export function PartnerDashboard() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void apiFetch<Dashboard>("/v1/partner/dashboard/")
      .then((data) => { setDashboard(data); setError(""); })
      .catch((caught) => setError(describeError(caught, "Le tableau de bord partenaire n’a pas pu être chargé.")));
  }, []);
  return <PartnerPageShell title="Tableau de bord" intro="Indicateurs calculés uniquement à partir du vendeur qui vous est attribué. Aucun chiffre n’est inventé.">
    <p role="note" className={noticeClass}>{RESERVATION_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {dashboard && <>
      <section aria-label="Indicateurs partenaire" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <article className={box}><p className="text-sm text-slate-600">Vendeur attribué</p><p className="mt-2 text-2xl font-bold">#{dashboard.seller_id}</p></article>
        <article className={box}><p className="text-sm text-slate-600">Produits publiés</p><p className="mt-2 text-2xl font-bold">{dashboard.products.published}</p></article>
        <article className={box}><p className="text-sm text-slate-600">Réservations à traiter</p><p className="mt-2 text-2xl font-bold">{dashboard.orders.awaiting_seller}</p></article>
        <article className={box}><p className="text-sm text-slate-600">Notifications non lues</p><p className="mt-2 text-2xl font-bold">{dashboard.unread_notifications}</p></article>
      </section>
      <section className={box}><h2 className="text-lg font-bold">File d’attente</h2><dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div><dt className="text-slate-500">Brouillons</dt><dd className="font-semibold">{dashboard.products.draft}</dd></div>
        <div><dt className="text-slate-500">En modération</dt><dd className="font-semibold">{dashboard.products.pending_moderation}</dd></div>
        <div><dt className="text-slate-500">Acceptées</dt><dd className="font-semibold">{dashboard.orders.accepted}</dd></div>
        <div><dt className="text-slate-500">Prêtes pour retrait</dt><dd className="font-semibold">{dashboard.orders.ready}</dd></div>
      </dl></section>
    </>}
  </PartnerPageShell>;
}

export function PartnerProducts() {
  const [products, setProducts] = useState<PartnerProduct[]>([]);
  const [productType, setProductType] = useState<"medicine" | "equipment">("equipment");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    return apiFetch<Page<PartnerProduct>>("/v1/partner/products/")
      .then((data) => { setProducts(data.results); setError(""); })
      .catch((caught) => setError(describeError(caught, "Vos produits n’ont pas pu être chargés.")));
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = productPayload(new FormData(form), productType);
      await apiMutate<PartnerProduct>("/v1/partner/products/", { method: "POST", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } });
      setMessage("Produit enregistré en brouillon. Soumettez-le à la modération pour publication.");
      form.reset();
      await refresh();
    } catch (caught) { setError(describeError(caught, "Le produit n’a pas pu être enregistré.")); }
    finally { setBusy(false); }
  }

  return <PartnerPageShell title="Mes produits" intro="Créez et suivez les fiches de votre vendeur. Le stock inconnu reste vide et n’est jamais remplacé par une valeur inventée.">
    <p role="note" className={noticeClass}>{PRESCRIPTION_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    <form onSubmit={create} className={`${box} space-y-4`}>
      <h2 className="text-xl font-bold">Nouvelle fiche</h2>
      <label className="block text-sm font-semibold">Type<select value={productType} onChange={(event) => setProductType(event.target.value as "medicine" | "equipment")} className={field}>
        <option value="equipment">Matériel médical</option><option value="medicine">Médicament</option>
      </select></label>
      <ProductFields productType={productType}/>
      <button disabled={busy} className={primaryButton}>{busy ? "Enregistrement…" : "Créer le brouillon"}</button>
    </form>
    <section className={box}>
      <h2 className="text-xl font-bold">Fiches enregistrées ({products.length})</h2>
      {products.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucun produit n’est encore enregistré pour votre vendeur.</p> : <ul className="mt-4 divide-y divide-slate-100">
        {products.map((product) => <li key={product.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div><p className="font-bold text-slate-900">{product.title}</p><p className="text-xs text-slate-600">{product.product_type_label} · {formatMGA(product.price_mga)} · stock {product.stock_quantity === null ? "non renseigné" : product.stock_quantity} · {moderationStatusLabel(product.moderation_status)}</p></div>
          <div className="flex flex-wrap gap-2"><Link href={`/partenaire/produits/${product.id}`} className={secondaryButton}>Modifier</Link><Link href={`/partenaire/images?product=${product.id}`} className={secondaryButton}>Images</Link></div>
        </li>)}
      </ul>}
    </section>
  </PartnerPageShell>;
}

export function PartnerProductEditor({ productId }: { productId: number }) {
  const [product, setProduct] = useState<PartnerProduct | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    return apiFetch<PartnerProduct>(`/v1/partner/products/${productId}/`)
      .then((data) => { setProduct(data); setError(""); })
      .catch((caught) => setError(describeError(caught, "Cette fiche n’est pas accessible.")));
  }, [productId]);
  useEffect(() => { void refresh(); }, [refresh]);

  async function mutate(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiMutate(path, init); setMessage(success); await refresh(); }
    catch (caught) { setError(describeError(caught, "La modification a échoué.")); }
    finally { setBusy(false); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!product) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = productPayload(new FormData(form), product.product_type);
      await apiMutate(`/v1/partner/products/${productId}/`, { method: "PATCH", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } });
      setMessage("Fiche mise à jour. Une modification substantielle remet le produit en attente de modération.");
      await refresh();
    } catch (caught) { setError(describeError(caught, "La fiche n’a pas pu être mise à jour.")); }
    finally { setBusy(false); }
  }

  if (!product) return <PartnerPageShell title="Produit" intro="Chargement de la fiche…">{error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}</PartnerPageShell>;

  return <PartnerPageShell title={product.title} intro={`Statut : ${product.moderation_status_label}. Les changements substantiels sont de nouveau soumis à modération.`}>
    <p role="note" className={noticeClass}>{RESERVATION_NOTICE}</p>
    {product.product_type === "medicine" && product.requires_prescription && <p role="note" className={noticeClass}>{PRESCRIPTION_NOTICE}</p>}
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    {product.review_notes && <p className={box}>Note de modération : {product.review_notes}</p>}
    <form onSubmit={save} className={`${box} space-y-4`}>
      <h2 className="text-xl font-bold">Modifier la fiche</h2>
      <ProductFields productType={product.product_type} product={product}/>
      <button disabled={busy} className={primaryButton}>Enregistrer les modifications</button>
    </form>
    <div className="grid gap-4 md:grid-cols-2">
      <section className={`${box} space-y-3`}><h2 className="text-lg font-bold">Stock et disponibilité</h2>
        <form onSubmit={(event) => {
          event.preventDefault();
          const value = String(new FormData(event.currentTarget).get("stock_quantity") ?? "").trim();
          void mutate(`/v1/partner/products/${productId}/stock/`, { method: "PATCH", body: JSON.stringify({ stock_quantity: value === "" ? null : Number(value) }), headers: { "Content-Type": "application/json" } }, "Stock mis à jour.");
        }} className="space-y-3">
          <label className="block text-sm font-semibold">Stock disponible (vide si inconnu)<input name="stock_quantity" type="number" min="0" step="1" defaultValue={product.stock_quantity ?? ""} className={field}/></label>
          <button disabled={busy} className={secondaryButton}>Mettre à jour le stock</button>
        </form>
        <form onSubmit={(event) => {
          event.preventDefault();
          const value = String(new FormData(event.currentTarget).get("availability") ?? "");
          void mutate(`/v1/partner/products/${productId}/availability/`, { method: "PATCH", body: JSON.stringify({ availability: value }), headers: { "Content-Type": "application/json" } }, "Disponibilité mise à jour.");
        }} className="space-y-3">
          <label className="block text-sm font-semibold">Disponibilité<select name="availability" defaultValue={product.availability} className={field}>
            <option value="available">Disponible</option><option value="limited">Disponibilité limitée</option><option value="unavailable">Indisponible</option>
          </select></label>
          <button disabled={busy} className={secondaryButton}>Mettre à jour la disponibilité</button>
        </form>
      </section>
      <section className={`${box} space-y-3`}><h2 className="text-lg font-bold">Modération</h2>
        <p className="text-sm text-slate-600">La soumission est possible tant que la fiche n’est pas archivée.</p>
        <button type="button" disabled={busy || !canSubmitForReview(product)} onClick={() => void mutate(`/v1/partner/products/${productId}/submit-review/`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }, "Produit soumis à la modération.")} className={primaryButton}>Soumettre à la modération</button>
        <button type="button" disabled={busy} onClick={() => {
          if (window.confirm("Archiver cette fiche ? Elle sera conservée sans suppression de données.")) void mutate(`/v1/partner/products/${productId}/`, { method: "DELETE" }, "Produit archivé.");
        }} className="rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700">Archiver</button>
        <Link href={`/partenaire/images?product=${product.id}`} className="block text-sm font-semibold text-blue-800">Gérer les images →</Link>
      </section>
    </div>
  </PartnerPageShell>;
}

export function PartnerImages({ initialProductId }: { initialProductId?: number }) {
  const [products, setProducts] = useState<PartnerProduct[]>([]);
  const [productId, setProductId] = useState<number | null>(initialProductId ?? null);
  const [images, setImages] = useState<PartnerImage[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void apiFetch<Page<PartnerProduct>>("/v1/partner/products/")
      .then((data) => { setProducts(data.results); setProductId((current) => current ?? data.results[0]?.id ?? null); })
      .catch((caught) => setError(describeError(caught, "Vos produits n’ont pas pu être chargés.")));
  }, []);

  const refreshImages = useCallback(() => {
    if (!productId) { setImages([]); return Promise.resolve(); }
    return apiFetch<Page<PartnerImage>>(`/v1/partner/products/${productId}/images/`)
      .then((data) => { setImages(data.results); setError(""); })
      .catch((caught) => setError(describeError(caught, "La galerie n’a pas pu être chargée.")));
  }, [productId]);
  useEffect(() => { void refreshImages(); }, [refreshImages]);

  async function mutate(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiMutate(path, init); setMessage(success); await refreshImages(); }
    catch (caught) { setError(describeError(caught, "L’opération a échoué.")); }
    finally { setBusy(false); }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!productId) return;
    const data = new FormData(form);
    const file = data.get("file");
    if (!(file instanceof File) || file.size === 0) { setError("Sélectionnez un fichier image."); return; }
    await mutate(`/v1/partner/products/${productId}/images/`, { method: "POST", body: data }, "Image privée ajoutée.");
    form.reset();
  }

  return <PartnerPageShell title="Galerie privée" intro="Les fichiers restent privés et ne sont accessibles qu’aux gestionnaires autorisés. L’image principale est synchronisée avec la fiche historique.">
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    <section className={`${box} space-y-3`}>
      <label className="block text-sm font-semibold">Produit<select value={productId ?? ""} onChange={(event) => setProductId(Number(event.target.value) || null)} className={field}>
        <option value="">Choisir un produit</option>{products.map((product) => <option key={product.id} value={product.id}>{product.title}</option>)}
      </select></label>
      {!productId && <p className="text-sm text-slate-600">Créez d’abord une fiche produit pour ajouter des images.</p>}
      {productId && <form onSubmit={upload} className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end">
        <label className="block text-sm font-semibold">Fichier JPEG, PNG ou WebP (2 Mo max)<input name="file" type="file" accept="image/jpeg,image/png,image/webp" required className="mt-1 block w-full text-sm"/></label>
        <label className="block text-sm font-semibold">Texte alternatif<input name="alt_text" maxLength={200} className={field}/></label>
        <label className="block text-sm font-semibold">Ordre<input name="sort_order" type="number" min="0" defaultValue={0} className={field}/></label>
        <button disabled={busy} className={primaryButton}>Ajouter</button>
      </form>}
    </section>
    {productId && <section className={box}><h2 className="text-lg font-bold">Images ({images.length})</h2>
      {images.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune image pour ce produit.</p> : <ul className="mt-4 divide-y divide-slate-100">
        {images.map((image) => <li key={image.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div><p className="text-sm font-semibold">{image.alt_text || "Image sans texte alternatif"}{image.is_primary && " · principale"}</p><a href={image.file_url} target="_blank" rel="noreferrer" className="text-xs font-semibold text-blue-800">Ouvrir le fichier privé</a></div>
          <div className="flex gap-2">
            {!image.is_primary && <button type="button" disabled={busy} onClick={() => void mutate(`/v1/partner/products/${productId}/images/${image.id}/primary/`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }, "Image principale définie.")} className={secondaryButton}>Définir principale</button>}
            <button type="button" disabled={busy} onClick={() => {
              if (window.confirm("Supprimer cette image de la galerie ?")) void mutate(`/v1/partner/products/${productId}/images/${image.id}/`, { method: "DELETE" }, "Image supprimée.");
            }} className="rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700">Supprimer</button>
          </div>
        </li>)}
      </ul>}
    </section>}
  </PartnerPageShell>;
}

export function PartnerPromotions() {
  const [promotions, setPromotions] = useState<PartnerPromotion[]>([]);
  const [products, setProducts] = useState<PartnerProduct[]>([]);
  const [editing, setEditing] = useState<PartnerPromotion | null>(null);
  const [results, setResults] = useState<Record<number, PromotionResult>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    return Promise.all([
      apiFetch<PartnerPromotion[]>("/v1/promotions/partner/"),
      apiFetch<Page<PartnerProduct>>("/v1/partner/products/"),
    ])
      .then(([promotionData, productData]) => {
        setPromotions(promotionData);
        setProducts(productData.results);
        setError("");
      })
      .catch((caught) => setError(describeError(caught, "Vos promotions n’ont pas pu être chargées.")));
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  async function mutate(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiMutate(path, init); setMessage(success); await refresh(); }
    catch (caught) { setError(describeError(caught, "L’opération a échoué.")); }
    finally { setBusy(false); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const maxRedemptions = String(values.get("max_redemptions") ?? "").trim();
    const payload = {
      product: Number(values.get("product") ?? 0),
      code: String(values.get("code") ?? ""),
      title: String(values.get("title") ?? ""),
      discount_type: String(values.get("discount_type") ?? "percent"),
      discount_value: String(values.get("discount_value") ?? ""),
      starts_at: fromDateTimeLocal(String(values.get("starts_at") ?? "")),
      ends_at: fromDateTimeLocal(String(values.get("ends_at") ?? "")),
      max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
    };
    if (editing && !canEditPromotion(editing)) { setError("Seules les promotions en attente ou refusées peuvent être modifiées."); return; }
    if (!payload.product || !payload.starts_at || !payload.ends_at) { setError("Sélectionnez un produit et des dates de début et de fin valides."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      if (editing) {
        await apiMutate(`/v1/promotions/partner/${editing.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
          headers: { "Content-Type": "application/json" },
        });
      } else {
        await apiMutate("/v1/promotions/partner/", {
          method: "POST",
          body: JSON.stringify(payload),
          headers: { "Content-Type": "application/json" },
        });
      }
      setMessage(editing ? "Promotion resoumise à la validation administrative." : "Promotion enregistrée en attente de validation administrative.");
      setEditing(null);
      await refresh();
    } catch (caught) {
      setError(describeError(caught, "La promotion n’a pas pu être enregistrée."));
    } finally {
      setBusy(false);
    }
  }

  async function loadResults(id: number) {
    setBusy(true); setError("");
    try {
      const data = await apiFetch<PromotionResult>(`/v1/promotions/partner/${id}/results/`);
      setResults((current) => ({ ...current, [id]: data }));
    } catch (caught) {
      setError(describeError(caught, "Les résultats de la promotion n’ont pas pu être chargés."));
    } finally {
      setBusy(false);
    }
  }

  const availableProducts = products.filter((product) => product.status !== "archived");

  return <PartnerPageShell title="Promotions" intro="Créez une offre pour l’un de vos produits, puis laissez l’administration centrale la valider avant toute activation publique.">
    <p role="note" className={noticeClass}>{PROMOTION_NOTICE} {COUPON_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    <form key={editing?.id ?? "new"} onSubmit={save} className={`${box} grid gap-3 sm:grid-cols-2`}>
      <div className="sm:col-span-2"><h2 className="text-xl font-bold">{editing ? "Modifier la promotion sélectionnée" : "Nouvelle promotion"}</h2><p className="mt-1 text-xs leading-5 text-slate-600">Le prix initial et le prix promotionnel sont calculés par le serveur à partir du prix de la fiche. Aucun montant n’est saisi ici.</p>{editing && <button type="button" onClick={() => setEditing(null)} className="mt-1 text-sm font-semibold text-blue-800">Annuler la modification</button>}</div>
      <label className="block text-sm font-semibold sm:col-span-2">Produit concerné<select name="product" required defaultValue={editing?.product ?? ""} className={field}><option value="">Choisir un produit</option>{availableProducts.map((product) => <option key={product.id} value={product.id}>{product.title} — {formatMGA(product.price_mga)}</option>)}</select></label>
      <label className="block text-sm font-semibold">Code coupon<input name="code" required maxLength={32} defaultValue={editing?.code ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Titre (facultatif)<input name="title" maxLength={120} defaultValue={editing?.title ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Type de remise<select name="discount_type" defaultValue={editing?.discount_type ?? "percent"} className={field}><option value="percent">Pourcentage (max. 90 %)</option><option value="fixed">Montant fixe en Ariary</option></select></label>
      <label className="block text-sm font-semibold">Valeur de la remise<input name="discount_value" type="number" min="0.01" step="0.01" required defaultValue={editing?.discount_value ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Début<input name="starts_at" type="datetime-local" required defaultValue={editing ? toDateTimeLocal(editing.starts_at) : ""} className={field}/></label>
      <label className="block text-sm font-semibold">Fin<input name="ends_at" type="datetime-local" required defaultValue={editing ? toDateTimeLocal(editing.ends_at) : ""} className={field}/></label>
      <label className="block text-sm font-semibold sm:col-span-2">Quantité maximale de réservations (laisser vide si illimitée)<input name="max_redemptions" type="number" min="1" step="1" defaultValue={editing?.max_redemptions ?? ""} className={field}/></label>
      <div className="sm:col-span-2"><button disabled={busy || availableProducts.length === 0} className={primaryButton}>{busy ? "Enregistrement…" : editing ? "Resoumettre la promotion" : "Créer la promotion"}</button>{availableProducts.length === 0 && <p className="mt-2 text-xs text-slate-600">Créez d’abord une fiche produit non archivée.</p>}</div>
    </form>
    <section className={box}>
      <h2 className="text-xl font-bold">Promotions enregistrées ({promotions.length})</h2>
      {promotions.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune promotion n’est encore enregistrée pour votre vendeur.</p> : <ul className="mt-4 divide-y divide-slate-100">
        {promotions.map((promotion) => {
          const conditions = promotionConditions(promotion);
          const result = results[promotion.id];
          return <li key={promotion.id} className="py-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-bold text-slate-900">{promotion.title}</p><p className="text-xs text-slate-600">{promotion.product_title} · code {promotion.code} · {promotionStatusLabel(promotion.status)}</p><p className="mt-1 text-sm"><span className="line-through text-slate-500">{formatMGA(promotion.original_price_mga)}</span> <span className="font-bold text-emerald-800">{formatMGA(promotion.promotional_price_mga)}</span> · {promotionDiscount(promotion)}</p>{conditions.length > 0 && <p className="mt-1 text-xs text-slate-600">{conditions.join(" · ")}</p>}{promotion.review_notes && <p className="mt-1 text-xs text-red-700">Note de l’administration : {promotion.review_notes}</p>}</div>
              <div className="flex flex-wrap gap-2">
                {canEditPromotion(promotion) && <button type="button" disabled={busy} onClick={() => setEditing(promotion)} className={secondaryButton}>Modifier</button>}
                {["approved", "paused"].includes(promotion.status) && <button type="button" disabled={busy} onClick={() => void mutate(`/v1/promotions/partner/${promotion.id}/activate/`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }, "Promotion activée et visible publiquement.")} className={primaryButton}>Activer</button>}
                {promotion.status === "active" && <button type="button" disabled={busy} onClick={() => void mutate(`/v1/promotions/partner/${promotion.id}/deactivate/`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }, "Promotion désactivée.")} className={secondaryButton}>Désactiver</button>}
                {canRequestPromotionRemoval(promotion) && <button type="button" disabled={busy} onClick={() => { if (window.confirm("Demander l’archivage de cette promotion ? L’administration centrale devra le valider.")) void mutate(`/v1/promotions/partner/${promotion.id}/request-removal/`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }, "Demande d’archivage transmise à l’administration."); }} className="rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700">Demander l’archivage</button>}
                <button type="button" disabled={busy} onClick={() => void loadResults(promotion.id)} className={secondaryButton}>Résultats</button>
              </div>
            </div>
            {result && <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-700"><p className="font-bold">Résultats enregistrés</p><p>Réservations : {result.redemption_count} · quantité utilisée : {result.quantity_used} · remise totale : {formatMGA(result.total_discount_mga)} · restante : {result.remaining_quantity ?? "illimitée"}</p></div>}
          </li>;
        })}
      </ul>}
    </section>
  </PartnerPageShell>;
}

export function PartnerOrders() {
  const [orders, setOrders] = useState<PartnerOrder[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    void apiFetch<PartnerOrder[]>("/v1/partner/orders/")
      .then((data) => { setOrders(data); setError(""); })
      .catch((caught) => setError(describeError(caught, "Les commandes n’ont pas pu être chargées.")));
  }, []);
  return <PartnerPageShell title="Commandes reçues" intro="Réservations envoyées par les clients pour votre vendeur. Aucun paiement n’est encaissé via FANAFODIKO.">
    <p role="note" className={noticeClass}>{NO_ONLINE_PAYMENT_NOTICE} {PICKUP_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    <section className={box}>
      {orders.length === 0 ? <p className="text-sm text-slate-600">Aucune réservation reçue pour le moment.</p> : <ul className="divide-y divide-slate-100">
        {orders.map((order) => <li key={order.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div><p className="font-bold text-slate-900">{order.reference}</p><p className="text-xs text-slate-600">{formatMarketplaceDate(order.created_at)} · {order.items.length} article(s) · {formatMGA(order.total_mga)}</p></div>
          <div className="flex items-center gap-3"><span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-800">{orderStatusLabel(order.status)}</span><Link href={`/partenaire/commandes/${order.id}`} className="text-sm font-semibold text-blue-800">Traiter →</Link></div>
        </li>)}
      </ul>}
    </section>
  </PartnerPageShell>;
}

export function PartnerOrderDetail({ orderId }: { orderId: number }) {
  const [order, setOrder] = useState<PartnerOrder | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [prescriptionChecked, setPrescriptionChecked] = useState(false);

  const refresh = useCallback(() => {
    return apiFetch<PartnerOrder>(`/v1/partner/orders/${orderId}/`)
      .then((data) => { setOrder(data); setError(""); })
      .catch((caught) => setError(describeError(caught, "Cette commande n’est pas accessible.")));
  }, [orderId]);
  useEffect(() => { void refresh(); }, [refresh]);

  async function transition(action: string, body: Record<string, unknown> = {}) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiMutate(`/v1/partner/orders/${orderId}/${action}/`, { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } });
      setMessage("Statut de la réservation mis à jour.");
      await refresh();
    } catch (caught) { setError(describeError(caught, "La transition n’a pas pu être appliquée.")); }
    finally { setBusy(false); }
  }

  if (!order) return <PartnerPageShell title="Commande" intro="Chargement de la réservation…">{error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}</PartnerPageShell>;

  const prescriptionItems = order.items.filter((item) => item.requires_prescription);
  const needsPrescription = prescriptionItems.length > 0;
  const prescriptionVerified = prescriptionItems.every((item) => item.prescription_checked_by_seller);
  const showPrescriptionCheck = needsPrescription && !prescriptionVerified;
  return <PartnerPageShell title={`Réservation ${order.reference}`} intro={`Statut actuel : ${orderStatusLabel(order.status)}.`}>
    <p role="note" className={noticeClass}>{RESERVATION_NOTICE}</p>
    {needsPrescription && <p role="note" className={noticeClass}>{PRESCRIPTION_NOTICE}</p>}
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    <section className={box}><h2 className="text-lg font-bold">Articles réservés</h2><ul className="mt-3 divide-y divide-slate-100">
      {order.items.map((item) => <li key={item.id} className="py-3 text-sm"><p className="font-semibold">{item.title} × {item.quantity}</p><p className="text-slate-600">{formatMGA(item.unit_price_mga)} · {formatMGA(item.line_total_mga)}{item.requires_prescription && ` · ordonnance ${item.prescription_checked_by_seller ? "vérifiée par le pharmacien" : "à vérifier"}`}</p></li>)}
    </ul><p className="mt-4 text-lg font-extrabold">Total : {formatMGA(order.total_mga)}</p>{order.customer_note && <p className="mt-2 text-sm text-slate-600">Note du client : {order.customer_note}</p>}{order.rejection_reason && <p className="mt-2 text-sm text-red-800">Motif du refus : {order.rejection_reason}</p>}</section>

    <section className={`${box} space-y-3`}><h2 className="text-lg font-bold">Traitement</h2>
      {showPrescriptionCheck && <label className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-950"><input type="checkbox" checked={prescriptionChecked} onChange={(event) => setPrescriptionChecked(event.target.checked)}/>Je confirme avoir vérifié l’ordonnance auprès du client</label>}
      {prescriptionVerified && <p className="text-sm font-semibold text-teal-800">Ordonnance déjà confirmée par le pharmacien pour tous les articles concernés.</p>}
      {order.status === "awaiting_seller" && <>
        <div className="flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => void transition("accept", { note: "", prescription_checked: prescriptionChecked })} className={primaryButton}>Accepter</button></div>
        <label className="block text-sm font-semibold">Motif du refus<input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} className={field}/></label>
        <button type="button" disabled={busy || !reason.trim()} onClick={() => void transition("reject", { reason })} className="rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700">Refuser</button>
      </>}
      {order.status === "accepted" && <button type="button" disabled={busy} onClick={() => void transition("prepare", prescriptionChecked ? { prescription_checked: true } : {})} className={primaryButton}>Passer en préparation</button>}
      {order.status === "preparing" && <button type="button" disabled={busy} onClick={() => void transition("mark-ready", prescriptionChecked ? { prescription_checked: true } : {})} className={primaryButton}>Marquer prête pour retrait</button>}
      {order.status === "ready" && <button type="button" disabled={busy} onClick={() => void transition("complete", prescriptionChecked ? { prescription_checked: true } : {})} className={primaryButton}>Finaliser après remise</button>}
      {["rejected", "completed", "cancelled"].includes(order.status) && <p className="text-sm text-slate-600">Aucune transition supplémentaire n’est autorisée pour ce statut.</p>}
    </section>

    <section className={box}><h2 className="text-lg font-bold">Suivi</h2>{order.events.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucun événement de suivi.</p> : <ol className="mt-3 space-y-2 text-sm">
      {order.events.map((event) => <li key={event.id} className="rounded-xl bg-slate-50 p-3"><p className="font-semibold">{orderHistoryFromLabel(event.from_status)} → {orderStatusLabel(event.to_status)}</p>{event.note && <p className="text-slate-600">{event.note}</p>}<p className="text-xs text-slate-500">{formatMarketplaceDate(event.created_at)}</p></li>)}
    </ol>}</section>
  </PartnerPageShell>;
}
