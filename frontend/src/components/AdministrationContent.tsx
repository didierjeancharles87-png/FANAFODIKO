"use client";

import Image from "next/image";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { MarketplaceAdmin } from "@/components/MarketplaceAdmin";

type FAQ = { id: number; question: string; answer: string; sort_order: number; is_visible: boolean };
type News = { id: number; title: string; slug: string; summary: string; body: string; is_published: boolean; published_at: string | null };
type SitePage = { id: number; page: string; title: string; introduction: string; body: string };
type SiteImage = { id: number; slot: string; url: string; alt_text: string; is_visible: boolean };
type Tab = "whatsapp" | "images" | "news" | "faqs" | "pages" | "marketplace";

const slots = [["teleconsultation", "Téléconsultation"], ["pharmacy", "Pharmacie"], ["laboratory", "Laboratoire"], ["dentistry", "Soins dentaires"], ["specialist", "Médecins et spécialistes"]];
const pages = [["home", "Accueil"], ["about", "À propos"], ["contact", "Contact"], ["terms", "Conditions"], ["privacy", "Confidentialité"]];
const box = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
const field = "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900";
const button = "rounded-lg bg-blue-800 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-900 disabled:opacity-60";

export function AdministrationContent() {
  const [tab, setTab] = useState<Tab>("whatsapp");
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [news, setNews] = useState<News[]>([]);
  const [pageContents, setPageContents] = useState<SitePage[]>([]);
  const [images, setImages] = useState<SiteImage[]>([]);
  const [whatsapp, setWhatsapp] = useState("");
  const [selectedFaq, setSelectedFaq] = useState<number | null>(null);
  const [selectedNews, setSelectedNews] = useState<number | null>(null);
  const [selectedPage, setSelectedPage] = useState("home");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [config, faqData, newsData, pageData, imageData] = await Promise.all([
        apiFetch<{ whatsapp_number: string; use_database_config: boolean }>("/v1/site-content/admin/configuration/"),
        apiFetch<FAQ[]>("/v1/site-content/admin/faqs/"),
        apiFetch<News[]>("/v1/site-content/admin/news/"),
        apiFetch<SitePage[]>("/v1/site-content/admin/pages/"),
        apiFetch<SiteImage[]>("/v1/site-content/admin/images/"),
      ]);
      setWhatsapp(config.whatsapp_number);
      setMessage(config.whatsapp_number ? "" : "WhatsApp n’est pas configuré. Saisissez un numéro international pour afficher le bouton public.");
      setFaqs(faqData); setNews(newsData); setPageContents(pageData); setImages(imageData);
      setError("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Les contenus ne peuvent pas être chargés. Vérifiez votre accès administrateur.");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function request<T>(path: string, init?: RequestInit) {
    await apiFetch("/v1/auth/csrf/");
    return apiFetch<T>(path, init);
  }

  async function save(path: string, init: RequestInit, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { await request(path, init); setMessage(success); await refresh(); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "La modification n’a pas pu être enregistrée."); }
    finally { setBusy(false); }
  }

  async function remove(path: string, success: string) {
    if (!window.confirm("Confirmer la suppression de ce contenu ?")) return;
    setBusy(true); setError(""); setMessage("");
    try { await request(path, { method: "DELETE" }); setMessage(success); setSelectedFaq(null); setSelectedNews(null); await refresh(); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "La suppression a échoué."); }
    finally { setBusy(false); }
  }

  function submitWhatsApp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void save("/v1/site-content/admin/configuration/", { method: "PATCH", body: JSON.stringify({ whatsapp_number: whatsapp }), headers: { "Content-Type": "application/json" } }, "Configuration WhatsApp enregistrée.");
  }

  function submitFaq(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const payload = { question: String(form.get("question")), answer: String(form.get("answer")), sort_order: Number(form.get("sort_order")), is_visible: form.get("is_visible") === "on" };
    const path = selectedFaq ? `/v1/site-content/admin/faqs/${selectedFaq}/` : "/v1/site-content/admin/faqs/";
    void save(path, { method: selectedFaq ? "PATCH" : "POST", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } }, "FAQ enregistrée.");
    setSelectedFaq(null); event.currentTarget.reset();
  }

  function submitNews(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const payload = { title: String(form.get("title")), summary: String(form.get("summary")), body: String(form.get("body")), is_published: form.get("is_published") === "on" };
    const path = selectedNews ? `/v1/site-content/admin/news/${selectedNews}/` : "/v1/site-content/admin/news/";
    void save(path, { method: selectedNews ? "PATCH" : "POST", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } }, "Actualité enregistrée.");
    setSelectedNews(null); event.currentTarget.reset();
  }

  function submitPage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const payload = { page: selectedPage, title: String(form.get("title")), introduction: String(form.get("introduction")), body: String(form.get("body")) };
    const existing = pageContents.find((item) => item.page === selectedPage);
    void save(existing ? `/v1/site-content/admin/pages/${existing.id}/` : "/v1/site-content/admin/pages/", { method: existing ? "PATCH" : "POST", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } }, "Texte de page enregistré.");
  }

  function submitImage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    void save("/v1/site-content/admin/images/", { method: "POST", body: form }, "Image ajoutée ou remplacée.");
    event.currentTarget.reset();
  }

  const faqBeingEdited = faqs.find((item) => item.id === selectedFaq);
  const newsBeingEdited = news.find((item) => item.id === selectedNews);
  const pageBeingEdited = pageContents.find((item) => item.page === selectedPage);
  const tabs: Array<[Tab, string]> = [["whatsapp", "WhatsApp"], ["images", "Images du site"], ["news", "Actualités"], ["faqs", "FAQ"], ["pages", "Textes des pages"], ["marketplace", "Marketplace"]];

  return <section className="mt-10" aria-labelledby="content-admin-heading">
    <h2 id="content-admin-heading" className="text-2xl font-bold tracking-tight">Gestion du contenu</h2>
    <p className="mt-2 text-sm text-slate-600">Ces changements sont enregistrés par le service et consignés dans l’audit d’administration.</p>
    {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
    {message && <p className="mt-4 rounded-xl border border-teal-200 bg-teal-50 p-3 text-sm text-teal-900" role="status">{message}</p>}
    <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Sections de gestion du contenu">{tabs.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === id ? "bg-blue-800 text-white" : "border border-slate-300 bg-white text-slate-700"}`} onClick={() => setTab(id)}>{label}</button>)}</div>

    {tab === "whatsapp" && <section className={`${box} mt-4 max-w-2xl`}><h3 className="text-lg font-bold">Numéro de contact WhatsApp</h3><p className="mt-1 text-sm text-slate-600">Format international, 8 à 15 chiffres. Laissez vide pour désactiver le lien.</p>{!whatsapp.trim() && <p role="status" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">WhatsApp n’est pas configuré. Le bouton public est masqué tant qu’un numéro international n’est pas enregistré.</p>}<form onSubmit={submitWhatsApp} className="mt-4"><label className="block text-sm font-semibold">Numéro<input value={whatsapp} onChange={(event) => setWhatsapp(event.target.value)} maxLength={20} placeholder="+261 …" className={field}/></label><button disabled={busy} className={`${button} mt-4`}>Enregistrer le numéro</button></form><p className="mt-3 text-xs text-slate-500">Seul ce numéro enregistré dans la configuration du site est utilisé. Aucun message n’est envoyé automatiquement : le bouton ouvre une conversation WhatsApp dans le navigateur.</p></section>}

    {tab === "faqs" && <div className="mt-4 grid gap-4 lg:grid-cols-2"><form onSubmit={submitFaq} className={`${box} space-y-3`}><h3 className="text-lg font-bold">{selectedFaq ? "Modifier une FAQ" : "Créer une FAQ"}</h3><label className="block text-sm font-semibold">Question<input name="question" key={`faq-q-${selectedFaq ?? "new"}`} defaultValue={faqBeingEdited?.question ?? ""} maxLength={300} required className={field}/></label><label className="block text-sm font-semibold">Réponse<textarea name="answer" key={`faq-a-${selectedFaq ?? "new"}`} defaultValue={faqBeingEdited?.answer ?? ""} maxLength={5000} required className={`${field} min-h-32`}/></label><label className="block text-sm font-semibold">Ordre<input name="sort_order" type="number" min="0" defaultValue={faqBeingEdited?.sort_order ?? 0} className={field}/></label><label className="flex items-center gap-2 text-sm"><input name="is_visible" type="checkbox" defaultChecked={faqBeingEdited?.is_visible ?? true}/>Visible publiquement</label><div className="flex gap-2"><button disabled={busy} className={button}>Enregistrer</button>{selectedFaq && <button type="button" onClick={() => setSelectedFaq(null)} className="rounded-lg border px-4 py-2 text-sm">Annuler</button>}</div></form><div className={`${box} space-y-3`}><h3 className="text-lg font-bold">FAQ existantes ({faqs.length})</h3>{faqs.map((item) => <article key={item.id} className="border-b border-slate-100 pb-3"><p className="font-semibold">{item.question}</p><p className="mt-1 text-sm text-slate-600">{item.answer}</p><p className="mt-1 text-xs text-slate-500">Ordre {item.sort_order} · {item.is_visible ? "Visible" : "Masquée"}</p><div className="mt-2 flex gap-3 text-sm"><button type="button" onClick={() => setSelectedFaq(item.id)} className="font-semibold text-blue-800">Modifier</button><button type="button" disabled={busy} onClick={() => void remove(`/v1/site-content/admin/faqs/${item.id}/`, "FAQ supprimée.")} className="font-semibold text-red-700">Supprimer</button></div></article>)}</div></div>}

    {tab === "news" && <div className="mt-4 grid gap-4 lg:grid-cols-2"><form onSubmit={submitNews} className={`${box} space-y-3`}><h3 className="text-lg font-bold">{selectedNews ? "Modifier une actualité" : "Créer une actualité"}</h3><label className="block text-sm font-semibold">Titre<input name="title" key={`news-title-${selectedNews ?? "new"}`} defaultValue={newsBeingEdited?.title ?? ""} maxLength={200} required className={field}/></label><label className="block text-sm font-semibold">Résumé<input name="summary" key={`news-summary-${selectedNews ?? "new"}`} defaultValue={newsBeingEdited?.summary ?? ""} maxLength={400} required className={field}/></label><label className="block text-sm font-semibold">Texte<textarea name="body" key={`news-body-${selectedNews ?? "new"}`} defaultValue={newsBeingEdited?.body ?? ""} maxLength={12000} required className={`${field} min-h-36`}/></label><label className="flex items-center gap-2 text-sm"><input name="is_published" type="checkbox" defaultChecked={newsBeingEdited?.is_published ?? false}/>Publier</label><div className="flex gap-2"><button disabled={busy} className={button}>Enregistrer</button>{selectedNews && <button type="button" onClick={() => setSelectedNews(null)} className="rounded-lg border px-4 py-2 text-sm">Annuler</button>}</div></form><div className={`${box} space-y-3`}><h3 className="text-lg font-bold">Actualités enregistrées ({news.length})</h3>{news.map((item) => <article key={item.id} className="border-b border-slate-100 pb-3"><p className="font-semibold">{item.title}</p><p className="text-sm text-slate-600">{item.summary}</p><p className="mt-1 text-xs text-slate-500">{item.is_published ? "Publiée" : "Brouillon"}</p><div className="mt-2 flex gap-3 text-sm"><button type="button" onClick={() => setSelectedNews(item.id)} className="font-semibold text-blue-800">Modifier</button><button type="button" disabled={busy} onClick={() => void remove(`/v1/site-content/admin/news/${item.id}/`, "Actualité supprimée.")} className="font-semibold text-red-700">Supprimer</button></div></article>)}</div></div>}

    {tab === "pages" && <form onSubmit={submitPage} className={`${box} mt-4 max-w-3xl space-y-3`}><h3 className="text-lg font-bold">Textes des pages</h3><label className="block text-sm font-semibold">Page<select value={selectedPage} onChange={(event) => setSelectedPage(event.target.value)} className={field}>{pages.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="block text-sm font-semibold">Titre<input key={`page-title-${selectedPage}`} name="title" defaultValue={pageBeingEdited?.title ?? ""} maxLength={200} required className={field}/></label><label className="block text-sm font-semibold">Introduction<textarea key={`page-intro-${selectedPage}`} name="introduction" defaultValue={pageBeingEdited?.introduction ?? ""} maxLength={600} className={`${field} min-h-20`}/></label><label className="block text-sm font-semibold">Texte complémentaire<textarea key={`page-body-${selectedPage}`} name="body" defaultValue={pageBeingEdited?.body ?? ""} maxLength={12000} className={`${field} min-h-40`}/></label><button disabled={busy} className={button}>{pageBeingEdited ? "Mettre à jour" : "Créer le contenu"}</button><p className="text-xs text-slate-500">Les pages À propos, Contact, Conditions et Confidentialité reprennent ces textes publics. Pour l’accueil, la page d’introduction utilise le titre et l’introduction enregistrés.</p></form>}

    {tab === "marketplace" && <MarketplaceAdmin />}

    {tab === "images" && <div className="mt-4 grid gap-4 lg:grid-cols-2"><form onSubmit={submitImage} className={`${box} space-y-3`}><h3 className="text-lg font-bold">Ajouter ou remplacer une image</h3><label className="block text-sm font-semibold">Emplacement<select name="slot" required className={field}>{slots.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="block text-sm font-semibold">Texte alternatif<input name="alt_text" required maxLength={240} className={field}/></label><label className="block text-sm font-semibold">Fichier (JPEG, PNG ou WebP, 8 Mo maximum)<input name="image" type="file" accept="image/jpeg,image/png,image/webp" required className="mt-2 block w-full text-sm"/></label><button disabled={busy} className={button}>Envoyer l’image</button></form><div className={`${box} space-y-3`}><h3 className="text-lg font-bold">Images en place ({images.length})</h3>{images.map((asset) => <article key={asset.id} className="flex items-center gap-3 border-b border-slate-100 pb-3">{asset.url ? <Image src={asset.url} alt={asset.alt_text} width={112} height={72} unoptimized className="h-16 w-24 rounded-lg object-cover"/> : <div aria-hidden="true" className="flex h-16 w-24 items-center justify-center rounded-lg bg-slate-100 text-center text-xs text-slate-500">Image retirée</div>}<div className="min-w-0 flex-1"><p className="font-semibold">{slots.find(([key]) => key === asset.slot)?.[1] ?? asset.slot}</p><p className="truncate text-xs text-slate-600">{asset.alt_text} · {asset.is_visible ? "Visible" : "Retirée du site"}</p><button type="button" disabled={busy || !asset.is_visible} onClick={() => void remove(`/v1/site-content/admin/images/${asset.id}/`, "Image retirée du site.")} className="mt-1 text-sm font-semibold text-red-700">Retirer du site</button></div></article>)}</div></div>}
  </section>;
}
