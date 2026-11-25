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
  orderConfirmationHref,
  orderStatusLabel,
  orderTimeline,
  orderTrackingHref,
} from "@/lib/phase7.mjs";
import { COUPON_NOTICE, PROMOTION_NOTICE, couponSummary, promotionConditions, promotionDiscount } from "@/lib/promotions.mjs";
import { PublicNavigation } from "@/components/PublicNavigation";

type CartPromotion = {
  id: number;
  code: string;
  title: string;
  discount_label: string;
  original_price_mga: string;
  promotional_price_mga: string;
  status: string;
};

type CartItem = {
  id: number;
  product: number;
  product_title: string;
  seller_name: string;
  quantity: number;
  stock_quantity: number | null;
  unit_price_mga: string;
  original_unit_price_mga?: string;
  discount_mga?: string;
  coupon_code?: string;
  line_total_mga: string;
};

type Cart = {
  id: number;
  items: CartItem[];
  item_count: number;
  subtotal_mga: string;
  discount_mga: string;
  total_mga: string;
  coupon_code: string;
  coupon_error: string | null;
  promotion: CartPromotion | null;
};

type BuyerAddress = {
  id: number;
  label: string;
  recipient_name: string;
  phone_number: string;
  country: number | null;
  region: string;
  city: string;
  neighbourhood: string;
  complement: string;
  is_primary: boolean;
  is_active: boolean;
};

type Country = { id: number; name_fr: string };

type OrderItem = {
  id: number;
  product: number;
  title: string;
  unit_price_mga: string;
  original_unit_price_mga: string;
  discount_mga: string;
  coupon_code: string;
  quantity: number;
  line_total_mga: string;
  requires_prescription: boolean;
  authorization_status: string;
  authorization_reference: string;
  prescription_checked_by_seller: boolean;
  prescription_checked_at: string | null;
};

type OrderEvent = { id: number; from_status: string; to_status: string; note: string; created_at: string };

type Order = {
  id: number;
  reference: string;
  status: string;
  subtotal_mga: string;
  discount_mga: string;
  total_mga: string;
  coupon_code: string;
  delivery_recipient: string;
  delivery_phone: string;
  delivery_country: string;
  delivery_region: string;
  delivery_city: string;
  delivery_neighbourhood: string;
  delivery_complement: string;
  customer_note: string;
  seller_note: string;
  rejection_reason: string;
  seller: number;
  seller_name: string;
  created_at: string;
  items: OrderItem[];
  events: OrderEvent[];
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

export function ClientPageShell({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  const links = [
    ["/patient/profil", "Mon profil"],
    ["/patient/adresses", "Adresses de retrait"],
    ["/panier", "Panier"],
    ["/commandes", "Mes réservations"],
    ["/promotions", "Promotions"],
    ["/medicaments", "Catalogue"],
  ] as const;
  return <>
    <PublicNavigation />
    <main className="min-h-screen bg-[#f4f9fc] px-5 py-10 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-bold uppercase tracking-wide text-blue-800">Espace client</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">{title}</h1>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">{intro}</p>
        <nav aria-label="Navigation réservation" className="mt-5 flex flex-wrap gap-2 border-b border-slate-200 pb-5">
          {links.map(([href, label]) => <Link key={href} href={href} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-blue-500 hover:text-blue-800">{label}</Link>)}
        </nav>
        <div className="mt-6 space-y-5">{children}</div>
      </div>
    </main>
  </>;
}

export function AddToCartButton({ productId, requiresPrescription, isOrderable = true, unavailableReason }: { productId: number; requiresPrescription: boolean; isOrderable?: boolean; unavailableReason?: string | null }) {
  const [quantity, setQuantity] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isOrderable) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiMutate("/v1/cart/", {
        method: "POST",
        body: JSON.stringify({ product: productId, quantity }),
        headers: { "Content-Type": "application/json" },
      });
      setMessage(`Article ajouté au panier. ${RESERVATION_NOTICE}`);
    } catch (caught) {
      setError(describeError(caught, "L’ajout au panier n’a pas pu être effectué."));
    } finally {
      setBusy(false);
    }
  }

  return <section className={`mt-6 rounded-2xl border p-4 ${isOrderable ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-slate-50"}`}>
    <h2 className="text-lg font-bold text-slate-950">{isOrderable ? "Réserver ce produit" : "Réservation indisponible"}</h2>
    {isOrderable ? <>
      <p role="note" className={`mt-2 ${noticeClass}`}>{RESERVATION_NOTICE}</p>
      {requiresPrescription && <p role="note" className={`mt-2 ${noticeClass}`}>{PRESCRIPTION_NOTICE}</p>}
      <form onSubmit={add} className="mt-3 flex flex-wrap items-end gap-3">
        <label className="block text-sm font-semibold">Quantité (1 à 99)<input type="number" min={1} max={99} value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} className={`${field} w-28`}/></label>
        <button disabled={busy || !Number.isInteger(quantity) || quantity < 1 || quantity > 99} className={primaryButton}>{busy ? "Ajout…" : "Ajouter au panier"}</button>
        <Link href="/panier" className={secondaryButton}>Voir le panier</Link>
      </form>
    </> : <>
      <p role="note" className="mt-2 rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700">{unavailableReason?.trim() || "Ce produit ne peut pas être réservé pour le moment."}</p>
      <p className="mt-2 text-xs leading-5 text-slate-600">La fiche reste consultable. Aucune réservation ne peut être créée tant que la commandabilité n’est pas rétablie par le vendeur.</p>
      <Link href="/panier" className={`mt-3 inline-flex ${secondaryButton}`}>Voir le panier</Link>
    </>}
    {error && <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="mt-3 rounded-xl border border-teal-200 bg-teal-50 p-3 text-sm text-teal-900">{message}</p>}
  </section>;
}

export function CartPage() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [confirmed, setConfirmed] = useState<Order[]>([]);
  const [addresses, setAddresses] = useState<BuyerAddress[]>([]);
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    return apiFetch<Cart>("/v1/cart/")
      .then((data) => {
        setCart(data);
        setCouponCode(data.coupon_code || "");
        setError("");
      })
      .catch((caught) => setError(describeError(caught, "Le panier n’a pas pu être chargé. Connectez-vous avec un compte patient.")));
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    void apiFetch<BuyerAddress[]>("/v1/accounts/patient/addresses/")
      .then((data) => {
        setAddresses(data);
        const primary = data.find((address) => address.is_primary && address.is_active !== false);
        setDeliveryAddress((current) => current || (primary ? String(primary.id) : ""));
      })
      .catch(() => setAddresses([]));
  }, []);

  async function mutate(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await apiMutate(path, init); setMessage(success); await refresh(); }
    catch (caught) { setError(describeError(caught, "L’opération a échoué.")); }
    finally { setBusy(false); }
  }

  async function checkout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const customerNote = String(new FormData(form).get("customer_note") ?? "");
    setBusy(true); setError(""); setMessage("");
    try {
      const orders = await apiMutate<Order[]>("/v1/orders/", {
        method: "POST",
        body: JSON.stringify({
          customer_note: customerNote,
          delivery_address: deliveryAddress ? Number(deliveryAddress) : null,
        }),
        headers: { "Content-Type": "application/json" },
      });
      setConfirmed(orders);
      setMessage("Réservation confirmée. Aucun paiement n’a été effectué.");
      form.reset();
      await refresh();
    } catch (caught) {
      setError(describeError(caught, "La réservation n’a pas pu être confirmée."));
    } finally {
      setBusy(false);
    }
  }

  return <ClientPageShell title="Panier" intro="Les prix et la commandabilité sont revérifiés par le serveur au moment de la réservation. Aucun stock n’est inventé.">
    <p role="note" className={noticeClass}>{RESERVATION_NOTICE}</p>
    <p role="note" className={noticeClass}>{PRESCRIPTION_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    {confirmed.length > 0 && <section className={box}><h2 className="text-xl font-bold">Réservations créées</h2><ul className="mt-3 space-y-2">
      {confirmed.map((order) => <li key={order.id} className="rounded-xl bg-slate-50 p-3 text-sm"><p className="font-bold">{order.reference} · {formatMGA(order.total_mga)}</p><div className="mt-2 flex flex-wrap gap-3"><Link href={orderConfirmationHref(order)} className="font-semibold text-blue-800">Confirmation →</Link><Link href={orderTrackingHref(order)} className="font-semibold text-blue-800">Suivi →</Link></div></li>)}
    </ul></section>}
    {cart && <>
      <section className={box}>
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-bold">Articles ({cart.item_count})</h2>{cart.items.length > 0 && <button type="button" disabled={busy} onClick={() => void mutate("/v1/cart/", { method: "DELETE" }, "Panier vidé.")} className="text-sm font-semibold text-red-700">Vider le panier</button>}</div>
        {cart.items.length === 0 ? <p className="mt-3 text-sm text-slate-600">Votre panier est vide. Choisissez une fiche dans le catalogue pour créer une réservation.</p> : <ul className="mt-4 divide-y divide-slate-100">
          {cart.items.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div><p className="font-bold text-slate-900">{item.product_title}</p><p className="text-xs text-slate-600">{item.seller_name} · {formatMGA(item.unit_price_mga)} · stock déclaré {item.stock_quantity === null ? "non renseigné" : item.stock_quantity}</p>{item.coupon_code && <p className="mt-1 text-xs font-bold text-emerald-800">Coupon {item.coupon_code} · remise {formatMGA(item.discount_mga ?? "0.00")}</p>}</div>
            <div className="flex flex-wrap items-center gap-2">
              <form onSubmit={(event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const quantity = Number(new FormData(form).get("quantity"));
                void mutate(`/v1/cart/items/${item.id}/`, { method: "PATCH", body: JSON.stringify({ quantity }), headers: { "Content-Type": "application/json" } }, "Quantité mise à jour.");
              }} className="flex items-end gap-2"><label className="block text-xs font-semibold">Qté<input name="quantity" type="number" min={1} max={99} defaultValue={item.quantity} className={`${field} w-20`}/></label><button disabled={busy} className={secondaryButton}>Modifier</button></form>
              <button type="button" disabled={busy} onClick={() => void mutate(`/v1/cart/items/${item.id}/`, { method: "DELETE" }, "Article retiré.")} className="text-sm font-semibold text-red-700">Retirer</button>
              <span className="font-bold text-slate-900">{formatMGA(item.line_total_mga)}</span>
            </div>
          </li>)}
        </ul>}
        <div className="mt-4 space-y-1 border-t border-slate-100 pt-4 text-sm"><p>Sous-total : {formatMGA(cart.subtotal_mga)}</p>{couponSummary(cart).applied && <p className="font-semibold text-emerald-800">Réduction : − {formatMGA(cart.discount_mga)}</p>}<p className="text-lg font-extrabold">Total : {formatMGA(cart.total_mga)}</p></div>
      </section>
      <section className={box}>
        <h2 className="text-xl font-bold">Coupon</h2>
        <p role="note" className={`mt-2 ${noticeClass}`}>{PROMOTION_NOTICE} {COUPON_NOTICE}</p>
        {cart.promotion && <p className="mt-3 text-sm font-semibold text-emerald-800">{cart.promotion.title} · {promotionDiscount(cart.promotion)} · {promotionConditions(cart.promotion).join(" · ")}</p>}
        {couponSummary(cart).error && <p role="alert" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">{couponSummary(cart).error} Retirez le coupon ou corrigez le panier avant de confirmer.</p>}
        <form onSubmit={(event) => {
          event.preventDefault();
          void mutate("/v1/cart/coupon/", { method: "POST", body: JSON.stringify({ code: couponCode }), headers: { "Content-Type": "application/json" } }, "Coupon appliqué par le serveur.");
        }} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="block text-sm font-semibold">Code coupon<input value={couponCode} onChange={(event) => setCouponCode(event.target.value)} maxLength={32} required className={`${field} w-56`}/></label>
          <button disabled={busy || !couponCode.trim()} className={primaryButton}>Appliquer</button>
          {couponSummary(cart).applied && <button type="button" disabled={busy} onClick={() => void mutate("/v1/cart/coupon/", { method: "DELETE" }, "Coupon retiré.")} className={secondaryButton}>Retirer le coupon</button>}
        </form>
      </section>
      {cart.items.length > 0 && <section className={box}>
        <h2 className="text-xl font-bold">Confirmer la réservation</h2>
        <form onSubmit={checkout} className="mt-4 space-y-3">
          <label className="block text-sm font-semibold">Adresse de retrait / contact<select value={deliveryAddress} onChange={(event) => setDeliveryAddress(event.target.value)} className={field}>
            <option value="">Aucune adresse enregistrée</option>
            {addresses.map((address) => <option key={address.id} value={address.id}>{address.label || address.recipient_name} — {address.city}{address.is_primary ? " (principale)" : ""}</option>)}
          </select></label>
          <Link href="/patient/adresses" className="text-sm font-semibold text-blue-800">Gérer mes adresses de retrait →</Link>
          <label className="block text-sm font-semibold">Note pour le vendeur (facultative)<textarea name="customer_note" rows={2} maxLength={1000} className={field}/></label>
          <button disabled={busy || Boolean(cart.coupon_error)} className={primaryButton}>{busy ? "Confirmation…" : "Confirmer la réservation"}</button>
          <p className="text-xs leading-5 text-slate-600">Aucun moyen de paiement n’est demandé. Le serveur recalcule les prix, la remise et le total à partir des fiches publiées.</p>
        </form>
      </section>}
    </>}
  </ClientPageShell>;
}

export function BuyerAddressBook() {
  const [addresses, setAddresses] = useState<BuyerAddress[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [editing, setEditing] = useState<BuyerAddress | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    return apiFetch<BuyerAddress[]>("/v1/accounts/patient/addresses/")
      .then((data) => { setAddresses(data); setError(""); })
      .catch((caught) => setError(describeError(caught, "Vos adresses n’ont pas pu être chargées. Connectez-vous avec un compte patient.")));
  }, []);
  useEffect(() => {
    void refresh();
    void apiFetch<Country[]>("/v1/reference/countries/").then(setCountries).catch(() => undefined);
  }, [refresh]);

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
    const country = String(values.get("country") ?? "");
    const payload = {
      label: String(values.get("label") ?? ""),
      recipient_name: String(values.get("recipient_name") ?? ""),
      phone_number: String(values.get("phone_number") ?? ""),
      country: country ? Number(country) : null,
      region: String(values.get("region") ?? ""),
      city: String(values.get("city") ?? ""),
      neighbourhood: String(values.get("neighbourhood") ?? ""),
      complement: String(values.get("complement") ?? ""),
      is_primary: values.get("is_primary") === "on",
    };
    setBusy(true); setError(""); setMessage("");
    try {
      if (editing) {
        await apiMutate(`/v1/accounts/patient/addresses/${editing.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
          headers: { "Content-Type": "application/json" },
        });
      } else {
        await apiMutate("/v1/accounts/patient/addresses/", {
          method: "POST",
          body: JSON.stringify(payload),
          headers: { "Content-Type": "application/json" },
        });
      }
      setMessage(editing ? "Adresse mise à jour." : "Adresse de retrait ajoutée.");
      setEditing(null);
      await refresh();
    } catch (caught) {
      setError(describeError(caught, "L’adresse n’a pas pu être enregistrée."));
    } finally {
      setBusy(false);
    }
  }

  return <ClientPageShell title="Adresses de retrait" intro="Ces coordonnées servent uniquement au retrait et au contact avec le partenaire. Aucune livraison n’est effectuée par FANAFODIKO.">
    <p role="note" className={noticeClass}>{PICKUP_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    <form key={editing?.id ?? "new"} onSubmit={save} className={`${box} grid gap-3 sm:grid-cols-2`}>
      <div className="sm:col-span-2"><h2 className="text-xl font-bold">{editing ? "Modifier l’adresse sélectionnée" : "Nouvelle adresse de retrait"}</h2>{editing && <button type="button" onClick={() => setEditing(null)} className="mt-1 text-sm font-semibold text-blue-800">Annuler la modification</button>}</div>
      <label className="block text-sm font-semibold">Libellé<input name="label" required maxLength={120} defaultValue={editing?.label ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Nom du destinataire<input name="recipient_name" required maxLength={150} defaultValue={editing?.recipient_name ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Téléphone<input name="phone_number" type="tel" required maxLength={20} defaultValue={editing?.phone_number ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Pays<select name="country" defaultValue={editing?.country ? String(editing.country) : ""} className={field}><option value="">Choisir</option>{countries.map((country) => <option key={country.id} value={country.id}>{country.name_fr}</option>)}</select></label>
      <label className="block text-sm font-semibold">Région<input name="region" maxLength={120} defaultValue={editing?.region ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Ville ou commune<input name="city" required maxLength={120} defaultValue={editing?.city ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold">Quartier<input name="neighbourhood" maxLength={120} defaultValue={editing?.neighbourhood ?? ""} className={field}/></label>
      <label className="block text-sm font-semibold sm:col-span-2">Complément<input name="complement" maxLength={200} defaultValue={editing?.complement ?? ""} className={field}/></label>
      <label className="flex items-center gap-2 text-sm font-semibold sm:col-span-2"><input name="is_primary" type="checkbox" defaultChecked={editing?.is_primary ?? false}/>Adresse principale</label>
      <div className="sm:col-span-2"><button disabled={busy} className={primaryButton}>{busy ? "Enregistrement…" : editing ? "Enregistrer les modifications" : "Ajouter l’adresse"}</button></div>
    </form>
    <section className={box}>
      <h2 className="text-xl font-bold">Adresses enregistrées ({addresses.length})</h2>
      {addresses.length === 0 ? <p className="mt-3 text-sm text-slate-600">Aucune adresse de retrait n’est encore enregistrée.</p> : <ul className="mt-4 divide-y divide-slate-100">
        {addresses.map((address) => <li key={address.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
          <div className="text-sm"><p className="font-bold text-slate-900">{address.label || address.recipient_name}{address.is_primary && <span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-900">Principale</span>}</p><p className="text-slate-600">{address.recipient_name} · {address.phone_number}</p><p className="text-slate-600">{[address.neighbourhood, address.city, address.region].filter(Boolean).join(", ")}</p>{address.complement && <p className="text-slate-500">{address.complement}</p>}</div>
          <div className="flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => setEditing(address)} className={secondaryButton}>Modifier</button>{!address.is_primary && <button type="button" disabled={busy} onClick={() => void mutate(`/v1/accounts/patient/addresses/${address.id}/primary/`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }, "Adresse principale définie.")} className={secondaryButton}>Définir principale</button>}<button type="button" disabled={busy} onClick={() => { if (window.confirm("Retirer cette adresse de votre carnet ?")) void mutate(`/v1/accounts/patient/addresses/${address.id}/`, { method: "DELETE" }, "Adresse retirée."); }} className="rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700">Supprimer</button></div>
        </li>)}
      </ul>}
    </section>
  </ClientPageShell>;
}

export function OrderDetail({ order, onUpdated, confirmed = false }: { order: Order; onUpdated?: (order: Order) => void; confirmed?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const prescriptionItems = order.items.filter((item) => item.requires_prescription);
  const steps = orderTimeline(order);
  const addressParts = [
    order.delivery_recipient ? `Destinataire : ${order.delivery_recipient}` : "",
    order.delivery_phone ? `Téléphone : ${order.delivery_phone}` : "",
    [order.delivery_neighbourhood, order.delivery_city, order.delivery_region, order.delivery_country].filter(Boolean).join(", "),
    order.delivery_complement,
  ].filter(Boolean);

  async function cancel() {
    setBusy(true); setError(""); setMessage("");
    try {
      const updated = await apiMutate<Order>(`/v1/orders/${order.id}/cancel/`, { method: "POST", body: JSON.stringify({ note: "" }), headers: { "Content-Type": "application/json" } });
      setMessage("Réservation annulée.");
      onUpdated?.(updated);
    } catch (caught) {
      setError(describeError(caught, "L’annulation n’a pas pu être effectuée."));
    } finally {
      setBusy(false);
    }
  }

  return <>
    {confirmed && <section className="rounded-2xl border border-teal-200 bg-teal-50 p-5"><h2 className="text-xl font-bold text-teal-950">Réservation confirmée</h2><p className="mt-2 text-sm leading-6 text-teal-950">Votre demande a été transmise au vendeur partenaire. Aucun paiement en ligne n’a été effectué.</p></section>}
    <p role="note" className={noticeClass}>{RESERVATION_NOTICE}</p>
    {prescriptionItems.length > 0 && <p role="note" className={noticeClass}>{PRESCRIPTION_NOTICE}</p>}
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">{message}</p>}
    <section className={box}>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-bold">{order.reference}</h2><p className="mt-1 text-sm text-slate-600">{order.seller_name} · créée le {formatMarketplaceDate(order.created_at)}</p></div><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-900">{orderStatusLabel(order.status)}</span></div>
      <ul className="mt-4 divide-y divide-slate-100 border-t border-slate-100">{order.items.map((item) => <li key={item.id} className="py-3 text-sm">
        <p className="font-semibold">{item.title} × {item.quantity}</p>
        <p className="text-slate-600">{item.original_unit_price_mga && item.original_unit_price_mga !== item.unit_price_mga && <span className="mr-1 line-through">{formatMGA(item.original_unit_price_mga)}</span>}{formatMGA(item.unit_price_mga)} · {formatMGA(item.line_total_mga)}{item.coupon_code && ` · coupon ${item.coupon_code}`}{item.requires_prescription && ` · ordonnance ${item.prescription_checked_by_seller ? "vérifiée par le pharmacien" : "à vérifier avant retrait"}`}</p>
        {item.discount_mga && item.discount_mga !== "0.00" && <p className="text-xs font-semibold text-emerald-800">Remise enregistrée : − {formatMGA(item.discount_mga)}</p>}
        {item.authorization_status && <p className="text-xs text-slate-500">AMM déclarée : {item.authorization_status}{item.authorization_reference ? ` · ${item.authorization_reference}` : ""}</p>}
      </li>)}</ul>
      <div className="mt-4 space-y-1 border-t border-slate-100 pt-4 text-sm">
        <p>Sous-total : {formatMGA(order.subtotal_mga)}</p>
        {order.coupon_code && <p className="font-semibold text-emerald-800">Réduction : − {formatMGA(order.discount_mga)} · coupon {order.coupon_code}</p>}
        <p className="text-lg font-extrabold">Total : {formatMGA(order.total_mga)}</p>
      </div>
      <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm">
        <p className="font-bold">Coordonnées de retrait / contact</p>
        {addressParts.length === 0 ? <p className="mt-1 text-slate-600">Aucune adresse n’a été enregistrée avec cette réservation.</p> : <ul className="mt-1 space-y-0.5 text-slate-600">{addressParts.map((part, index) => <li key={`${part}-${index}`}>{part}</li>)}</ul>}
        <p className="mt-2 text-xs text-slate-500">Coordonnées figées au moment de la réservation ; elles ne reflètent pas les modifications ultérieures du carnet.</p>
      </div>
      {order.customer_note && <p className="mt-2 text-sm text-slate-600">Votre note : {order.customer_note}</p>}
      {order.seller_note && <p className="mt-2 text-sm text-slate-600">Note du vendeur : {order.seller_note}</p>}
      {order.rejection_reason && <p className="mt-2 text-sm text-red-800">Motif du refus : {order.rejection_reason}</p>}
      {order.status === "awaiting_seller" && <button type="button" disabled={busy} onClick={() => void cancel()} className="mt-4 rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700">Annuler la réservation</button>}
    </section>
    <section className={box}>
      <h2 className="text-lg font-bold">Suivi de la réservation</h2>
      {!["awaiting_seller", "accepted", "preparing", "ready", "completed"].includes(order.status) && <p role="note" className={`mt-2 ${noticeClass}`}>Statut final : {orderStatusLabel(order.status)}.</p>}
      <ol className="mt-4 space-y-3 text-sm">
        {steps.map((step, index) => <li key={step.status} className="flex gap-3">
          <span aria-hidden="true" className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${step.current ? "bg-blue-800 text-white" : step.done ? "bg-teal-700 text-white" : "bg-slate-100 text-slate-500"}`}>{step.done || step.current ? "✓" : index + 1}</span>
          <div>
            <p className={`font-semibold ${step.current ? "text-blue-900" : step.done ? "text-teal-900" : "text-slate-500"}`}>{step.label}{step.current && " · statut actuel"}</p>
            {step.at && <p className="text-xs text-slate-500">{formatMarketplaceDate(step.at)}</p>}
            {step.note && <p className="text-slate-600">{step.note}</p>}
          </div>
        </li>)}
      </ol>
      {order.events.length === 0 && <p className="mt-3 text-sm text-slate-600">Aucun événement de suivi n’a encore été enregistré.</p>}
    </section>
  </>;
}

export function ClientOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    void apiFetch<Order[]>("/v1/orders/")
      .then((data) => { setOrders(data); setError(""); })
      .catch((caught) => setError(describeError(caught, "Vos réservations n’ont pas pu être chargées.")));
  }, []);
  return <ClientPageShell title="Mes réservations" intro="Historique des demandes réelles créées depuis votre panier. Aucune donnée de paiement n’est conservée.">
    <p role="note" className={noticeClass}>{NO_ONLINE_PAYMENT_NOTICE} {PICKUP_NOTICE}</p>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    <section className={box}>
      {orders.length === 0 ? <p className="text-sm text-slate-600">Aucune réservation enregistrée pour votre compte.</p> : <ul className="divide-y divide-slate-100">
        {orders.map((order) => <li key={order.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="font-bold text-slate-900">{order.reference}</p><p className="text-xs text-slate-600">{order.seller_name} · {formatMarketplaceDate(order.created_at)} · {formatMGA(order.total_mga)}</p></div><div className="flex items-center gap-3"><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-900">{orderStatusLabel(order.status)}</span><Link href={orderTrackingHref(order)} className="text-sm font-semibold text-blue-800">Suivre →</Link></div></li>)}
      </ul>}
    </section>
  </ClientPageShell>;
}

export function ClientOrderLookup({ reference, confirmed = false }: { reference: string; confirmed?: boolean }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    return apiFetch<Order[]>("/v1/orders/")
      .then(async (orders) => {
        const match = orders.find((candidate) => candidate.reference === reference);
        if (!match) { setOrder(null); setError("Aucune réservation ne correspond à cette référence."); return; }
        const fresh = await apiFetch<Order>(`/v1/orders/${match.id}/`);
        setOrder(fresh); setError("");
      })
      .catch((caught) => setError(describeError(caught, "Cette réservation n’a pas pu être chargée.")));
  }, [reference]);
  useEffect(() => { void refresh(); }, [refresh]);

  return <ClientPageShell title={confirmed ? "Confirmation de réservation" : "Suivi de réservation"} intro="Le suivi est fourni par le serveur et reflète uniquement les événements enregistrés.">
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {!error && !order && <p className="text-sm text-slate-600">Chargement de la réservation…</p>}
    {order && <OrderDetail order={order} confirmed={confirmed} onUpdated={(updated) => setOrder(updated)}/>}
  </ClientPageShell>;
}
