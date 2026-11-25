"use client";

import Image from "next/image";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { statusLabel } from "@/lib/status-labels.mjs";

type Page<T> = { count: number; results: T[] };
type OptionSet = { countries: Array<{ id: number; name_fr: string }>; pharmacies: Array<{ id: number; name: string; city: string; verification_status: string; is_active: boolean; eligible: boolean }>; accounts: AccountChoice[] };
type AccountChoice = { id: number; username: string; email: string; professional_profile: number | null; professional_name: string; professional_status: string };
type Seller = { id: number; kind: "pharmacy" | "medical_supplier"; professional_profile: number | null; professional_name: string; professional_status: string; name: string; country: number; country_name: string; region: string; city: string; verification_status: string; verification_status_label: string; verification_reference: string; is_active: boolean; is_catalog_verified: boolean };
type Product = { id: number; product_type: "medicine" | "equipment"; product_type_label: string; title: string; slug: string; seller: number; seller_name: string; seller_status: string; seller_is_verified: boolean; price_mga: string; availability: string; status: string; status_label: string; moderation_status: string; moderation_status_label: string; is_sponsored: boolean; price_updated_at: string; availability_updated_at: string; image_url: string | null; active_ingredient: string; authorization_status: string; authorization_status_label: string; authorization_reference: string; authorization_verified_reference: string; authorization_review_notes: string; authorization_reviewed_at: string | null; authorization_decision_tracked: boolean; equipment_category: string };
type AuthorizationItem = { id: number; title: string; seller_name: string; authorization_status: string; authorization_status_label: string; authorization_reference: string; authorization_submitted_at: string | null; updated_at: string };
type AdminTab = "sellers" | "products" | "authorizations";
const box = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
const field = "mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-500";
const button = "rounded-xl bg-blue-800 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-900 disabled:opacity-50";

function errorText(error: unknown) {
  if (error instanceof ApiError) {
    if (error.details) return `${error.message} ${JSON.stringify(error.details)}`;
    return error.message;
  }
  return "La modification n’a pas pu être enregistrée.";
}

export function MarketplaceAdmin() {
  const [tab, setTab] = useState<AdminTab>("products");
  const [options, setOptions] = useState<OptionSet>({ countries: [], pharmacies: [], accounts: [] });
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [authorizations, setAuthorizations] = useState<AuthorizationItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [kind, setKind] = useState<Seller["kind"]>("pharmacy");
  const [productType, setProductType] = useState<Product["product_type"]>("medicine");

  const refresh = useCallback(async () => {
    try {
      const [optionData, sellerData, productData, authorizationData] = await Promise.all([
        apiFetch<OptionSet>("/v1/marketplace/admin/options/"),
        apiFetch<Page<Seller>>("/v1/marketplace/admin/sellers/"),
        apiFetch<Page<Product>>("/v1/marketplace/admin/products/"),
        apiFetch<Page<AuthorizationItem>>("/v1/admin/marketplace/authorizations/"),
      ]);
      setOptions(optionData); setSellers(sellerData.results); setProducts(productData.results);
      setAuthorizations(authorizationData.results); setError("");
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Le catalogue d’administration n’a pas pu être chargé."); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function mutate(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      if (init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase())) await apiFetch("/v1/auth/csrf/");
      await apiFetch(path, init); setMessage(success); await refresh();
    } catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  function createSeller(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    void mutate("/v1/marketplace/admin/sellers/", { method: "POST", body: JSON.stringify({
      kind, name: String(values.name ?? ""), professional_profile: kind === "pharmacy" ? Number(values.professional_profile) || null : null,
      country: Number(values.country), region: String(values.region ?? ""), city: String(values.city ?? ""),
      verification_reference: String(values.verification_reference ?? ""), verification_status: "pending",
    }), headers: { "Content-Type": "application/json" } }, "Vendeur ajouté en attente de vérification.");
    event.currentTarget.reset();
  }

  function createProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const specsText = String(form.get("technical_specifications") ?? "{}");
    let specs: Record<string, string | number | boolean> = {};
    try { specs = JSON.parse(specsText) as typeof specs; }
    catch { setError("Les caractéristiques techniques doivent respecter le format JSON objet."); return; }
    const payload = {
      product_type: productType, title: String(form.get("title") ?? ""), brand: String(form.get("brand") ?? ""),
      description: String(form.get("description") ?? ""), seller: Number(form.get("seller")), price_mga: String(form.get("price_mga") ?? ""),
      availability: String(form.get("availability") ?? "unavailable"), status: String(form.get("status") ?? "draft"),
      is_sponsored: form.get("is_sponsored") === "on", active_ingredient: String(form.get("active_ingredient") ?? ""),
      dosage: String(form.get("dosage") ?? ""), pharmaceutical_form: String(form.get("pharmaceutical_form") ?? ""),
      packaging: String(form.get("packaging") ?? ""), requires_prescription: form.get("requires_prescription") === "on",
      equipment_category: String(form.get("equipment_category") ?? ""), model_name: String(form.get("model_name") ?? ""),
      technical_specifications: specs, warranty: String(form.get("warranty") ?? ""),
    };
    const image = form.get("image");
    const body: BodyInit = image instanceof File && image.size > 0
      ? (() => { const data = new FormData(); for (const [key, value] of Object.entries(payload)) data.set(key, typeof value === "object" ? JSON.stringify(value) : String(value)); data.set("image", image); return data; })()
      : JSON.stringify(payload);
    const headers = body instanceof FormData ? undefined : { "Content-Type": "application/json" };
    void mutate("/v1/marketplace/admin/products/", { method: "POST", body, headers }, "Fiche enregistrée.");
    event.currentTarget.reset();
  }

  function changeSellerStatus(seller: Seller, verification_status: string) {
    void mutate(`/v1/marketplace/admin/sellers/${seller.id}/`, { method: "PATCH", body: JSON.stringify({ verification_status }), headers: { "Content-Type": "application/json" } }, "Statut du vendeur mis à jour.");
  }

  function changeProductStatus(product: Product, status: string) {
    void mutate(`/v1/marketplace/admin/products/${product.id}/`, { method: "PATCH", body: JSON.stringify({ status }), headers: { "Content-Type": "application/json" } }, "Statut de la fiche mis à jour.");
  }

  function moderateProduct(product: Product, decision: "approve" | "reject", success: string) {
    const reason = decision === "reject" ? window.prompt("Motif du refus de modération (obligatoire) :") ?? "" : "";
    if (decision === "reject" && !reason.trim()) { setError("Le motif du refus est obligatoire."); return; }
    const body = decision === "reject" ? { reason } : {};
    void mutate(`/v1/admin/marketplace/products/${product.id}/${decision}/`, { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }, success);
  }

  function reviewAuthorization(item: AuthorizationItem, decision: "verify" | "reject" | "reopen") {
    const reason = decision === "reject" ? window.prompt("Motif du refus AMM (obligatoire) :") ?? "" : "";
    if (decision === "reject" && !reason.trim()) { setError("Le motif du refus AMM est obligatoire."); return; }
    const success = decision === "verify"
      ? `AMM ${statusLabel("authorization", "verified")}.`
      : decision === "reject"
        ? `AMM ${statusLabel("authorization", "rejected")}.`
        : "AMM rouverte : une nouvelle vérification est requise.";
    const body = decision === "reject" ? { reason } : {};
    void mutate(`/v1/admin/marketplace/products/${item.id}/authorization/${decision}/`, { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }, success);
  }

  function archiveProduct(product: Product) {
    if (window.confirm("Archiver cette fiche ? Elle sera masquée du catalogue public et conservée dans l’administration.")) {
      void mutate(`/v1/marketplace/admin/products/${product.id}/`, { method: "DELETE" }, "Fiche archivée.");
    }
  }

  function deactivateSeller(seller: Seller) {
    if (window.confirm("Désactiver ce vendeur ? Ses fiches ne seront plus publiques et ses données seront conservées.")) {
      void mutate(`/v1/marketplace/admin/sellers/${seller.id}/`, { method: "DELETE" }, "Vendeur désactivé.");
    }
  }

  const verifiedSellers = sellers.filter((seller) => seller.is_active && seller.is_catalog_verified);
  return <section className="mt-8" aria-labelledby="marketplace-admin-heading">
    <h2 id="marketplace-admin-heading" className="text-2xl font-bold tracking-tight">Gestion du catalogue Marketplace</h2>
    <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">Les fiches commencent en brouillon. Pour publier un médicament, vérifiez l’AMM et le profil pharmacie. Les réservations sans paiement en ligne sont traitées dans l’espace partenaire ; aucune donnée d’ordonnance n’est collectée ici. Les actions sont consignées dans l’audit.</p>
    {error && <p role="alert" className="mt-4 break-words rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="mt-4 rounded-xl border border-teal-200 bg-teal-50 p-3 text-sm text-teal-900">{message}</p>}
    <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Gestion du catalogue"><button role="tab" aria-selected={tab === "products"} className={`${button} ${tab !== "products" ? "border border-slate-300 bg-white !text-slate-700" : ""}`} onClick={() => setTab("products")} type="button">Produits ({products.length})</button><button role="tab" aria-selected={tab === "authorizations"} className={`${button} ${tab !== "authorizations" ? "border border-slate-300 bg-white !text-slate-700" : ""}`} onClick={() => setTab("authorizations")} type="button">AMM à décider ({authorizations.length})</button><button role="tab" aria-selected={tab === "sellers"} className={`${button} ${tab !== "sellers" ? "border border-slate-300 bg-white !text-slate-700" : ""}`} onClick={() => setTab("sellers")} type="button">Vendeurs ({sellers.length})</button></div>

    {tab === "sellers" && <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]"><form onSubmit={createSeller} className={`${box} space-y-3`}><h3 className="text-lg font-bold">Ajouter un vendeur réel</h3><p className="text-xs leading-5 text-slate-600">Pour une pharmacie, choisissez un profil existant. Un fournisseur doit être vérifié par l’administration avant toute publication. N’ajoutez aucun vendeur sans vérification.</p><label className="block text-sm font-semibold">Type<select value={kind} onChange={(event) => setKind(event.target.value as Seller["kind"])} className={field}><option value="pharmacy">Pharmacie inscrite</option><option value="medical_supplier">Fournisseur de matériel médical</option></select></label>{kind === "pharmacy" ? <label className="block text-sm font-semibold">Profil pharmacie<select name="professional_profile" required className={field}><option value="">Choisir une pharmacie</option>{options.pharmacies.filter((item) => item.eligible).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.city || "Ville non renseignée"} · {statusLabel("professionalVerification", item.verification_status)}{item.is_active ? "" : " · compte inactif"}</option>)}</select></label> : <label className="block text-sm font-semibold">Nom légal du fournisseur<input name="name" required maxLength={180} className={field}/></label>}<label className="block text-sm font-semibold">Pays<select name="country" required className={field}><option value="">Choisir un pays</option>{options.countries.map((country) => <option key={country.id} value={country.id}>{country.name_fr}</option>)}</select></label><div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm font-semibold">Région<input name="region" maxLength={120} className={field}/></label><label className="block text-sm font-semibold">Ville<input name="city" required maxLength={120} className={field}/></label></div>{kind === "medical_supplier" && <label className="block text-sm font-semibold">Référence de vérification<input name="verification_reference" maxLength={160} placeholder="Demandée avant la validation" className={field}/></label>}<button disabled={busy} className={button}>Ajouter en attente</button></form>
      <div className={`${box} space-y-3`}><h3 className="text-lg font-bold">Vendeurs enregistrés</h3>{sellers.length === 0 ? <p className="text-sm text-slate-600">Aucun vendeur n’est encore enregistré.</p> : sellers.map((seller) => <article key={seller.id} className="rounded-xl border border-slate-100 p-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-bold text-slate-900">{seller.name}</h4><p className="mt-1 text-xs text-slate-600">{seller.kind === "pharmacy" ? "Pharmacie" : "Fournisseur matériel médical"} · {seller.city}, {seller.country_name}</p><p className="mt-1 text-xs text-slate-600">{seller.verification_status_label} · {seller.is_catalog_verified ? "Vendeur publiable" : "Non publiable"}{!seller.is_active ? " · désactivé" : ""}</p>{seller.kind === "pharmacy" && <p className="text-xs text-slate-500">Profil : {seller.professional_name} · statut {statusLabel("professionalVerification", seller.professional_status)}</p>}{seller.verification_reference && <p className="text-xs text-slate-500">Réf. {seller.verification_reference}</p>}</div><div className="flex flex-wrap gap-2">{seller.verification_status !== "verified" && seller.is_active && <button type="button" disabled={busy} onClick={() => changeSellerStatus(seller, "verified")} className="rounded-lg bg-teal-700 px-3 py-2 text-xs font-bold text-white">Vérifier</button>}{seller.verification_status === "verified" && <button type="button" disabled={busy} onClick={() => changeSellerStatus(seller, "rejected")} className="rounded-lg border border-amber-300 px-3 py-2 text-xs font-bold text-amber-900">Révoquer</button>}{seller.is_active && <button type="button" disabled={busy} onClick={() => deactivateSeller(seller)} className="rounded-lg border border-red-200 px-3 py-2 text-xs font-bold text-red-700">Désactiver</button>}</div></div></article>)}</div>
    </div>}

    {tab === "authorizations" && <div className={`${box} mt-4 space-y-3`}>
      <h3 className="text-lg font-bold">Décisions AMM</h3>
      <p className="text-xs leading-5 text-slate-600">Seule l’administration peut vérifier une AMM. Une modification de la référence par le partenaire remet la fiche en attente et nécessite une nouvelle décision.</p>
      {authorizations.length === 0 ? <p className="text-sm text-slate-600">Aucune AMM en attente de décision.</p> : authorizations.map((item) => <article key={item.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-100 p-3">
        <div className="min-w-0"><h4 className="font-bold text-slate-900">{item.title}</h4><p className="mt-1 text-xs text-slate-600">{item.seller_name} · {item.authorization_status_label || statusLabel("authorization", item.authorization_status)}</p><p className="mt-1 text-xs text-slate-500">Référence déclarée : {item.authorization_reference || "non renseignée"}{item.authorization_submitted_at ? " · transmise" : ""}</p></div>
        <div className="flex flex-wrap gap-2"><button type="button" disabled={busy || !item.authorization_reference.trim()} onClick={() => reviewAuthorization(item, "verify")} className="rounded-lg bg-teal-700 px-3 py-2 text-xs font-bold text-white">{statusLabel("authorization", "verified")}</button><button type="button" disabled={busy} onClick={() => reviewAuthorization(item, "reject")} className="rounded-lg border border-amber-300 px-3 py-2 text-xs font-bold text-amber-900">Refuser</button>{item.authorization_status !== "pending" && <button type="button" disabled={busy} onClick={() => reviewAuthorization(item, "reopen")} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700">Rouvrir</button>}</div>
      </article>)}
    </div>}

    {tab === "products" && <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]"><form onSubmit={createProduct} className={`${box} space-y-3`}><h3 className="text-lg font-bold">Créer une fiche</h3><label className="block text-sm font-semibold">Type<select value={productType} onChange={(event) => setProductType(event.target.value as Product["product_type"])} className={field}><option value="medicine">Médicament</option><option value="equipment">Matériel médical</option></select></label><label className="block text-sm font-semibold">Nom de la fiche<input name="title" required maxLength={180} className={field}/></label><div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm font-semibold">Marque ou laboratoire<input name="brand" maxLength={160} className={field}/></label><label className="block text-sm font-semibold">Prix (Ariary)<input name="price_mga" type="number" min="0.01" step="0.01" required className={field}/></label></div><label className="block text-sm font-semibold">Vendeur vérifié<select name="seller" required className={field}><option value="">Choisir un vendeur</option>{verifiedSellers.map((seller) => <option key={seller.id} value={seller.id}>{seller.name} · {seller.city}</option>)}</select></label><div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm font-semibold">Disponibilité<select name="availability" defaultValue="unavailable" className={field}><option value="available">Disponible</option><option value="limited">Disponibilité limitée</option><option value="unavailable">Indisponible</option></select></label><label className="block text-sm font-semibold">Statut<select name="status" defaultValue="draft" className={field}><option value="draft">Brouillon</option><option value="published">Publier</option></select></label></div><label className="block text-sm font-semibold">Description<textarea name="description" maxLength={4000} rows={3} className={field}/></label>
      {productType === "medicine" ? <fieldset className="grid gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 sm:grid-cols-2"><legend className="px-1 text-sm font-bold text-amber-950">Informations du médicament</legend><label className="block text-sm font-semibold">Principe actif<input name="active_ingredient" required maxLength={180} className={field}/></label><label className="block text-sm font-semibold">Dosage<input name="dosage" required maxLength={120} placeholder="Ex. dosage déclaré" className={field}/></label><label className="block text-sm font-semibold">Forme pharmaceutique<input name="pharmaceutical_form" required maxLength={120} className={field}/></label><label className="block text-sm font-semibold">Conditionnement<input name="packaging" required maxLength={160} className={field}/></label><label className="block text-sm font-semibold">Statut de l’AMM<span className="text-xs text-amber-950">décision administrative</span></label><p className="col-span-full text-xs leading-5 text-amber-950">La référence AMM est déclarée par le partenaire, puis décidée dans l’onglet AMM. Aucune publication de médicament n’est possible avant vérification.</p><label className="col-span-full flex items-center gap-2 text-sm font-semibold text-slate-800"><input name="requires_prescription" type="checkbox" defaultChecked/>Ordonnance nécessaire</label></fieldset> : <fieldset className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:grid-cols-2"><legend className="px-1 text-sm font-bold text-slate-800">Informations du matériel médical</legend><label className="block text-sm font-semibold">Catégorie<select name="equipment_category" required className={field}><option value="">Choisir</option><option value="diagnostic">Diagnostic</option><option value="monitoring">Surveillance médicale</option><option value="mobility">Mobilité et transfert</option><option value="protection">Protection</option><option value="consumables">Consommables</option><option value="other">Autre matériel</option></select></label><label className="block text-sm font-semibold">Marque et modèle<input name="model_name" maxLength={160} className={field}/></label><label className="col-span-full block text-sm font-semibold">Caractéristiques techniques (objet JSON)<textarea name="technical_specifications" defaultValue="{}" maxLength={5000} rows={3} className={field}/></label><label className="col-span-full block text-sm font-semibold">Garantie, si applicable<input name="warranty" maxLength={240} className={field}/></label></fieldset>}
      <label className="block text-sm font-semibold">Image facultative (JPEG, PNG ou WebP, 2 Mo maximum)<input name="image" type="file" accept="image/jpeg,image/png,image/webp" className="mt-1 block w-full text-sm text-slate-700"/></label><label className="flex items-center gap-2 text-sm font-semibold"><input name="is_sponsored" type="checkbox"/>Fiche sponsorisée (sera signalée publiquement)</label><button disabled={busy || verifiedSellers.length === 0} className={button}>Enregistrer la fiche</button>{verifiedSellers.length === 0 && <p className="text-xs text-amber-900">Ajoutez et vérifiez un vendeur avant de créer une fiche publiable.</p>}</form>
      <div className={`${box} space-y-3`}><h3 className="text-lg font-bold">Fiches ({products.length})</h3>{products.length === 0 ? <p className="text-sm text-slate-600">Aucune fiche n’est enregistrée. Aucun exemple fictif n’est préchargé.</p> : products.map((product) => <article key={product.id} className="flex gap-3 border-b border-slate-100 pb-3">{product.image_url && <Image src={product.image_url} alt="" width={72} height={72} unoptimized className="h-16 w-16 rounded-lg object-cover"/>}<div className="min-w-0 flex-1"><h4 className="font-bold text-slate-900">{product.title}</h4><p className="text-xs text-slate-600">{product.product_type_label} · {product.seller_name} · {Number(product.price_mga).toLocaleString("fr-MG")} Ar · {product.status_label}</p>{product.product_type === "medicine" && <p className="text-xs text-slate-500">{product.active_ingredient} · AMM {product.authorization_status_label || statusLabel("authorization", product.authorization_status)}{product.authorization_verified_reference ? ` · vérifiée : ${product.authorization_verified_reference}` : product.authorization_reference ? ` · déclarée : ${product.authorization_reference}` : ""}{product.authorization_review_notes ? ` · motif : ${product.authorization_review_notes}` : ""}</p>}<div className="mt-2 flex flex-wrap gap-2">{product.status !== "published" && <button type="button" disabled={busy || (product.product_type === "medicine" && product.authorization_status !== "verified")} title={product.product_type === "medicine" && product.authorization_status !== "verified" ? "AMM non vérifiée : décision administrative requise." : undefined} onClick={() => product.moderation_status === "pending" ? moderateProduct(product, "approve", "Produit approuvé et publié après modération.") : changeProductStatus(product, "published")} className="rounded-lg bg-teal-700 px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50">Publier</button>}{product.status === "published" && <button type="button" disabled={busy} onClick={() => changeProductStatus(product, "draft")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-bold text-slate-700">Dépublier</button>}{product.status !== "archived" && <button type="button" disabled={busy} onClick={() => archiveProduct(product)} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-bold text-red-700">Archiver</button>}</div></div></article>)}</div></div>}
  </section>;
}
