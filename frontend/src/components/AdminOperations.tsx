"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, API_BASE_URL, apiFetch, apiMutate } from "@/lib/api";
import { formatMGA } from "@/lib/marketplace.mjs";
import { PROMOTION_NOTICE, promotionConditions, promotionDiscount, promotionStatusLabel } from "@/lib/promotions.mjs";
import { orderStatusLabel, statusLabel } from "@/lib/status-labels.mjs";

type Page<T> = { count: number; results: T[] };
type Verification = { id: number; user_id: number; user_email: string; category: string; organization_name: string; license_number: string; status: string; created_at: string; reviewed_at: string | null; review_notes: string };
type Professional = { id: number; legal_name: string; category_label: string; verification_status: string; account_status: string; is_complete: boolean; missing_information: string[]; user_email: string; city: string };
type Document = { id: number; profile_id: number; profile_name: string; category: string; document_type: string; original_filename: string; review_status: string; download_url: string; created_at: string };
type Seller = { id: number; name: string; kind: string; city: string; verification_status: string; verification_reference: string; is_active: boolean; is_catalog_verified: boolean; professional_name: string; professional_status: string };
type AccountChoice = { id: number; username: string; email: string; professional_name: string; professional_status: string };
type Options = { accounts: AccountChoice[] };
type ModerationProduct = { id: number; title: string; product_type_label: string; seller_name: string; authorization_status: string; authorization_reference: string; price_mga: string; submitted_for_review_at: string };
type Order = { id: number; reference: string; status: string; total_mga: string; seller_name: string; created_at: string };
type Promotion = { id: number; code: string; title: string; seller_name: string; product_title: string; discount_label: string; original_price_mga: string; promotional_price_mga: string; starts_at: string; ends_at: string; max_redemptions: number | null; remaining_quantity: number | null; status: string; status_label: string; review_notes: string; created_at: string };
type Notification = { id: number; notification_type_label: string; title: string; body: string; link: string | null; whatsapp_link: string | null; read_at: string | null; created_at: string };
type AdminTab = "verifications" | "professionals" | "sellers" | "moderation" | "promotions" | "orders" | "notifications";

const box = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
const field = "mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900";
const primary = "rounded-xl bg-emerald-700 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-800 disabled:opacity-50";
const secondary = "rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const danger = "rounded-xl border border-red-200 px-3 py-2 text-xs font-bold text-red-700 hover:bg-red-50 disabled:opacity-50";

function describe(caught: unknown, fallback: string) {
  if (caught instanceof ApiError) return caught.details ? `${caught.message} ${JSON.stringify(caught.details)}` : caught.message;
  return fallback;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("fr-MG");
}

const tabs: Array<[AdminTab, string]> = [
  ["verifications", "Demandes professionnelles"],
  ["professionals", "Professionnels"],
  ["sellers", "Partenaires"],
  ["moderation", "Modération produits"],
  ["promotions", "Promotions"],
  ["orders", "Réservations"],
  ["notifications", "Notifications"],
];

export function AdminOperations() {
  const [tab, setTab] = useState<AdminTab>("verifications");
  const [verifications, setVerifications] = useState<Verification[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [accounts, setAccounts] = useState<AccountChoice[]>([]);
  const [moderation, setModeration] = useState<ModerationProduct[]>([]);
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [verificationData, professionalData, documentData, sellerData, optionData, moderationData, promotionData, orderData, notificationData] = await Promise.all([
        apiFetch<Page<Verification>>("/v1/admin/professional-verifications/"),
        apiFetch<Page<Professional>>("/v1/professionals/admin/profiles/"),
        apiFetch<Page<Document>>("/v1/professionals/admin/documents/"),
        apiFetch<Page<Seller>>("/v1/marketplace/admin/sellers/"),
        apiFetch<Options>("/v1/marketplace/admin/options/"),
        apiFetch<Page<ModerationProduct>>("/v1/admin/marketplace/moderation/"),
        apiFetch<Promotion[]>("/v1/promotions/admin/"),
        apiFetch<Order[] | Page<Order>>("/v1/admin/orders/"),
        apiFetch<Notification[] | Page<Notification>>("/v1/notifications/"),
      ]);
      setVerifications(verificationData.results);
      setProfessionals(professionalData.results);
      setDocuments(documentData.results);
      setSellers(sellerData.results);
      setAccounts(optionData.accounts ?? []);
      setModeration(moderationData.results);
      setPromotions(promotionData);
      setOrders(Array.isArray(orderData) ? orderData : orderData.results ?? []);
      setNotifications(Array.isArray(notificationData) ? notificationData : notificationData.results ?? []);
      setError("");
    } catch (caught) {
      setError(describe(caught, "Les opérations d’administration n’ont pas pu être chargées."));
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function act(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiMutate(path, init);
      setMessage(success);
      await refresh();
    } catch (caught) {
      setError(describe(caught, "L’action n’a pas pu être effectuée."));
    } finally {
      setBusy(false);
    }
  }

  function review(verification: Verification, status: "approved" | "rejected") {
    const notes = status === "rejected" ? window.prompt("Motif du refus (obligatoire) :") ?? "" : "Validation de test depuis l’interface d’administration.";
    if (status === "rejected" && !notes.trim()) { setError("Le motif du refus est obligatoire."); return; }
    void act(`/v1/admin/professional-verifications/${verification.id}/review/`, {
      method: "POST",
      body: JSON.stringify({ status, notes }),
      headers: { "Content-Type": "application/json" },
    }, status === "approved" ? "Demande approuvée et compte placé dans le groupe professional_verified." : "Demande refusée.");
  }

  function changeSeller(seller: Seller, verification_status: string) {
    void act(`/v1/marketplace/admin/sellers/${seller.id}/`, {
      method: "PATCH",
      body: JSON.stringify({ verification_status }),
      headers: { "Content-Type": "application/json" },
    }, verification_status === "verified" ? "Partenaire vérifié." : "Vérification révoquée.");
  }

  function assignOwner(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const sellerId = Number(values.get("seller"));
    const accountId = Number(values.get("account"));
    if (!sellerId || !accountId) { setError("Sélectionnez un partenaire et un compte."); return; }
    void act(`/v1/admin/marketplace/sellers/${sellerId}/assign-owner/`, {
      method: "POST",
      body: JSON.stringify({ account: accountId }),
      headers: { "Content-Type": "application/json" },
    }, "Compte associé au vendeur. L’espace partenaire est maintenant accessible à ce compte.");
    form.reset();
  }

  function moderate(product: ModerationProduct, decision: "approve" | "reject") {
    const reason = decision === "reject" ? window.prompt("Motif du refus de publication :") ?? "" : "";
    if (decision === "reject" && !reason.trim()) { setError("Le motif du refus est obligatoire."); return; }
    void act(`/v1/admin/marketplace/products/${product.id}/${decision}/`, {
      method: "POST",
      body: JSON.stringify(decision === "reject" ? { reason } : {}),
      headers: { "Content-Type": "application/json" },
    }, decision === "approve" ? "Produit approuvé et publié." : "Produit refusé et renvoyé en brouillon.");
  }

  function reviewPromotion(promotion: Promotion, decision: "approve" | "reject") {
    const reason = decision === "reject" ? window.prompt("Motif du refus de la promotion :") ?? "" : "";
    if (decision === "reject" && !reason.trim()) { setError("Le motif du refus est obligatoire."); return; }
    void act(`/v1/promotions/admin/${promotion.id}/${decision}/`, {
      method: "POST",
      body: JSON.stringify(decision === "reject" ? { reason } : {}),
      headers: { "Content-Type": "application/json" },
    }, decision === "approve" ? "Promotion validée. L’activation publique reste au vendeur partenaire." : "Promotion refusée avec motif enregistré.");
  }

  function archivePromotion(promotion: Promotion) {
    if (!window.confirm("Archiver définitivement cette promotion ? Aucune donnée ne sera supprimée physiquement.")) return;
    void act(`/v1/promotions/admin/${promotion.id}/archive/`, {
      method: "POST",
      body: JSON.stringify({}),
      headers: { "Content-Type": "application/json" },
    }, "Archivage validé et enregistré dans l’audit.");
  }

  return <section className="mt-8" aria-labelledby="admin-operations-heading">
    <h2 id="admin-operations-heading" className="text-2xl font-bold tracking-tight">Opérations d’administration</h2>
    <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">Ces actions utilisent les règles métier existantes : groupes de professionnels, `SellerOwner`, contrôle AMM, modération obligatoire et journalisation dans l’audit. Aucune donnée n’est créée ici à des fins de démonstration.</p>
    {error && <p role="alert" className="mt-4 break-words rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="mt-4 rounded-xl border border-teal-200 bg-teal-50 p-3 text-sm text-teal-900">{message}</p>}
    <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Opérations d’administration">
      {tabs.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)} className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === id ? "bg-emerald-700 text-white" : "border border-slate-300 bg-white text-slate-700"}`}>{label}</button>)}
    </div>

    {tab === "verifications" && <div className={`${box} mt-4`}>
      <h3 className="text-lg font-bold">Demandes de validation professionnelle</h3>
      {verifications.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune demande enregistrée.</p> : <ul className="mt-3 divide-y divide-slate-100">{verifications.map((item) => <li key={item.id} className="py-3">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-bold">{item.organization_name}</p><p className="text-xs text-slate-600">{item.user_email} · catégorie {item.category} · licence {item.license_number || "non renseignée"}</p><p className="text-xs text-slate-500">Créée le {formatDate(item.created_at)} · statut {statusLabel("confirmation", item.status)}</p>{item.review_notes && <p className="text-xs text-slate-500">Note : {item.review_notes}</p>}</div>
          <div className="flex flex-wrap gap-2">{item.status === "pending" && <><button type="button" disabled={busy} onClick={() => review(item, "approved")} className={primary}>Valider</button><button type="button" disabled={busy} onClick={() => review(item, "rejected")} className={danger}>Refuser</button></>}</div>
        </div>
      </li>)}</ul>}
    </div>}

    {tab === "professionals" && <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <div className={box}><h3 className="text-lg font-bold">Profils professionnels ({professionals.length})</h3>
        {professionals.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucun profil enregistré.</p> : <ul className="mt-3 divide-y divide-slate-100">{professionals.map((profile) => <li key={profile.id} className="py-3"><p className="font-bold">{profile.legal_name}</p><p className="text-xs text-slate-600">{profile.category_label} · {profile.user_email} · {profile.city || "ville non renseignée"}</p><p className="text-xs text-slate-600">Vérification {statusLabel("professionalVerification", profile.verification_status)} · compte {statusLabel("account", profile.account_status)} · {profile.is_complete ? "profil complet" : `champs manquants : ${profile.missing_information.join(", ")}`}</p>
          <div className="mt-2 flex flex-wrap gap-2">{profile.account_status === "active" && <button type="button" disabled={busy} onClick={() => { const reason = window.prompt("Motif de la suspension :") ?? ""; void act(`/v1/professionals/admin/profiles/${profile.id}/suspend/`, { method: "POST", body: JSON.stringify({ reason }), headers: { "Content-Type": "application/json" } }, "Compte professionnel suspendu."); }} className={danger}>Suspendre</button>}{profile.account_status === "suspended" && <button type="button" disabled={busy} onClick={() => act(`/v1/professionals/admin/profiles/${profile.id}/reactivate/`, { method: "POST", body: JSON.stringify({}), headers: { "Content-Type": "application/json" } }, "Compte professionnel réactivé.")} className={primary}>Réactiver</button>}</div>
        </li>)}</ul>}
      </div>
      <div className={box}><h3 className="text-lg font-bold">Justificatifs privés ({documents.length})</h3>
        {documents.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucun justificatif déposé.</p> : <ul className="mt-3 divide-y divide-slate-100">{documents.map((document) => <li key={document.id} className="py-3"><p className="text-sm font-semibold">{document.profile_name} · {document.document_type}</p><p className="text-xs text-slate-600">{document.original_filename} · {statusLabel("documentReview", document.review_status)} · {formatDate(document.created_at)}</p><a href={`${API_BASE_URL}${document.download_url}`} className="mt-1 inline-block text-xs font-bold text-emerald-800">Télécharger →</a></li>)}</ul>}
      </div>
    </div>}

    {tab === "sellers" && <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <div className={box}><h3 className="text-lg font-bold">Pharmacies et fournisseurs ({sellers.length})</h3>
        {sellers.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucun partenaire enregistré.</p> : <ul className="mt-3 divide-y divide-slate-100">{sellers.map((seller) => <li key={seller.id} className="py-3"><p className="font-bold">{seller.name}</p><p className="text-xs text-slate-600">{seller.kind === "pharmacy" ? "Pharmacie" : "Fournisseur"} · {seller.city} · vérification {statusLabel("sellerVerification", seller.verification_status)} · {seller.is_catalog_verified ? "publiable" : "non publiable"}{seller.verification_reference ? ` · réf. ${seller.verification_reference}` : ""}</p>{seller.professional_name && <p className="text-xs text-slate-500">Profil : {seller.professional_name} · {statusLabel("professionalVerification", seller.professional_status)}</p>}
          <div className="mt-2 flex flex-wrap gap-2">{seller.verification_status !== "verified" && seller.is_active && <button type="button" disabled={busy} onClick={() => changeSeller(seller, "verified")} className={primary}>Vérifier</button>}{seller.verification_status === "verified" && <button type="button" disabled={busy} onClick={() => changeSeller(seller, "rejected")} className={secondary}>Révoquer</button>}</div>
        </li>)}</ul>}
      </div>
      <form onSubmit={assignOwner} className={`${box} space-y-3`}><h3 className="text-lg font-bold">Associer un compte à un vendeur</h3><p className="text-xs leading-5 text-slate-600">L’assignation est la seule source d’accès à l’espace partenaire. Une pharmacie ne peut être associée qu’à un profil pharmacie approuvé.</p>
        <label className="block text-sm font-semibold">Partenaire<select name="seller" required className={field}><option value="">Choisir un vendeur</option>{sellers.map((seller) => <option key={seller.id} value={seller.id}>{seller.name}</option>)}</select></label>
        <label className="block text-sm font-semibold">Compte partenaire<select name="account" required className={field}><option value="">Choisir un compte</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.username} · {account.email}{account.professional_name ? ` · ${account.professional_name} (${statusLabel("professionalVerification", account.professional_status)})` : ""}</option>)}</select></label>
        <button disabled={busy} className={primary}>Associer le compte</button>
      </form>
    </div>}

    {tab === "moderation" && <div className={`${box} mt-4`}><h3 className="text-lg font-bold">File de modération ({moderation.length})</h3>
      {moderation.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucun produit en attente de modération.</p> : <ul className="mt-3 divide-y divide-slate-100">{moderation.map((product) => <li key={product.id} className="py-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-bold">{product.title}</p><p className="text-xs text-slate-600">{product.product_type_label} · {product.seller_name} · {Number(product.price_mga).toLocaleString("fr-MG")} Ar</p><p className="text-xs text-slate-500">Soumis le {formatDate(product.submitted_for_review_at)}{product.product_type_label === "Médicament" ? ` · AMM ${statusLabel("authorization", product.authorization_status)} (${product.authorization_reference || "référence manquante"})` : ""}</p></div>
        <div className="flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => moderate(product, "approve")} className={primary}>Approuver et publier</button><button type="button" disabled={busy} onClick={() => moderate(product, "reject")} className={danger}>Refuser</button></div></div></li>)}</ul>}
    </div>}

    {tab === "promotions" && <div className={`${box} mt-4`}>
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-bold">Promotions à superviser ({promotions.length})</h3><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-900">Validation centrale obligatoire</span></div>
      <p role="note" className="mt-2 max-w-3xl rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-950">{PROMOTION_NOTICE}</p>
      {promotions.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune promotion enregistrée.</p> : <ul className="mt-3 divide-y divide-slate-100">{promotions.map((promotion) => <li key={promotion.id} className="py-3">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-bold">{promotion.title} · {promotion.code}</p><p className="text-xs text-slate-600">{promotion.seller_name} · {promotion.product_title} · {promotionStatusLabel(promotion.status)}</p><p className="mt-1 text-sm"><span className="line-through text-slate-500">{formatMGA(promotion.original_price_mga)}</span> <span className="font-bold text-emerald-800">{formatMGA(promotion.promotional_price_mga)}</span> · {promotionDiscount(promotion)}</p><p className="text-xs text-slate-500">Du {formatDate(promotion.starts_at)} au {formatDate(promotion.ends_at)}{promotion.remaining_quantity !== null ? ` · ${promotion.remaining_quantity} restante(s)` : ""}</p>{promotionConditions(promotion).length > 0 && <p className="text-xs text-slate-600">{promotionConditions(promotion).join(" · ")}</p>}{promotion.review_notes && <p className="mt-1 text-xs text-red-700">Note de décision : {promotion.review_notes}</p>}</div>
          <div className="flex flex-wrap gap-2">{promotion.status === "pending" && <><button type="button" disabled={busy} onClick={() => reviewPromotion(promotion, "approve")} className={primary}>Valider</button><button type="button" disabled={busy} onClick={() => reviewPromotion(promotion, "reject")} className={danger}>Refuser</button></>}{promotion.status === "removal_requested" && <button type="button" disabled={busy} onClick={() => archivePromotion(promotion)} className={danger}>Valider l’archivage</button>}{!["pending", "removal_requested"].includes(promotion.status) && <span className="text-xs text-slate-500">Aucune action centrale requise.</span>}</div>
        </div>
      </li>)}</ul>}
    </div>}

    {tab === "orders" && <div className={`${box} mt-4`}><h3 className="text-lg font-bold">Réservations suivies ({orders.length})</h3>
      {orders.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune réservation enregistrée.</p> : <ul className="mt-3 divide-y divide-slate-100">{orders.map((order) => <li key={order.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="font-bold">{order.reference}</p><p className="text-xs text-slate-600">{order.seller_name} · {formatDate(order.created_at)} · {Number(order.total_mga).toLocaleString("fr-MG")} Ar</p></div><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-900">{orderStatusLabel(order.status)}</span></li>)}</ul>}
    </div>}

    {tab === "notifications" && <div className={`${box} mt-4`}><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-bold">Notifications ({notifications.length})</h3><button type="button" disabled={busy} onClick={() => act("/v1/notifications/read-all/", { method: "POST", body: JSON.stringify({}), headers: { "Content-Type": "application/json" } }, "Toutes les notifications sont marquées comme lues.")} className={secondary}>Tout marquer comme lu</button></div>
      {notifications.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune notification pour ce compte.</p> : <ul className="mt-3 divide-y divide-slate-100">{notifications.map((notification) => <li key={notification.id} className="py-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-bold">{notification.title}</p><p className="text-sm text-slate-700">{notification.body}</p><p className="text-xs text-slate-500">{notification.notification_type_label} · {formatDate(notification.created_at)} · {notification.read_at ? "lue" : "non lue"}</p>{notification.whatsapp_link && <p className="mt-1 text-xs text-slate-600">Lien WhatsApp consentement : <a href={notification.whatsapp_link} target="_blank" rel="noopener noreferrer" className="font-bold text-emerald-800">ouvrir →</a></p>}</div>{!notification.read_at && <button type="button" disabled={busy} onClick={() => act(`/v1/notifications/${notification.id}/read/`, { method: "POST", body: JSON.stringify({}), headers: { "Content-Type": "application/json" } }, "Notification marquée comme lue.")} className={secondary}>Marquer comme lue</button>}</div></li>)}</ul>}
    </div>}
  </section>;
}
