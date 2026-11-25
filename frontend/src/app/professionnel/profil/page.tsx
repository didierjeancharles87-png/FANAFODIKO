"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { ApiError, API_BASE_URL, apiFetch } from "@/lib/api";

type CategoryCode = "pharmacy" | "doctor" | "dentist" | "laboratory" | "delivery_courier" | "delivery_company";
type Profile = {
  id: number; category: CategoryCode; category_label: string; legal_name: string; manager_name: string; contact_phone: string; contact_email: string;
  country: number | null; region: string; city: string; address: string; latitude: string | null; longitude: string | null; description: string;
  details: Record<string, unknown>; verification_status: "draft" | "pending" | "approved" | "rejected"; is_complete: boolean; missing_information: string[];
};
type Country = { id: number; code_alpha2: string; name_fr: string; name_en: string };
type Document = { id: number; document_type: string; original_filename: string; size_bytes: number; review_status: string; download_url: string };
type FormValues = Record<string, string>;

const detailLabels: Record<string, string> = {
  commercial_name: "Nom commercial", license_number: "Numéro de licence (si applicable)", opening_hours: "Horaires d’ouverture (JSON)",
  specialty: "Spécialité", registration_number: "Numéro d’inscription (si applicable)", establishment_name: "Établissement ou cabinet", availability_info: "Informations de disponibilité",
  services: "Types de services ou analyses (séparés par des virgules)", service_areas: "Zones desservies (JSON)", delivery_types: "Types de livraison (séparés par des virgules)", transport_modes: "Moyens de transport (séparés par des virgules)",
};
const missingLabels: Record<string, string> = {
  legal_name: "Nom ou raison sociale", manager_name: "Responsable", contact_phone: "Téléphone", contact_email: "E-mail", country: "Pays", region: "Région", city: "Ville", address: "Adresse", commercial_name: "Nom commercial", opening_hours: "Horaires d’ouverture", specialty: "Spécialité", establishment_name: "Établissement ou cabinet", services: "Services proposés", service_areas: "Zones desservies", delivery_types: "Types de livraison", transport_modes: "Moyens de transport", supporting_document: "Au moins un justificatif",
};
const documentTypes = [["license", "Licence ou autorisation"], ["diploma", "Diplôme"], ["identity", "Pièce d’identité"], ["registration", "Inscription professionnelle"], ["facility", "Document de l’établissement"], ["other", "Autre justificatif"]];

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function listValue(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : "";
}

function inputClass() { return "mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-500 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"; }

export default function ProfessionalProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [countries, setCountries] = useState<Country[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [form, setForm] = useState<FormValues>({});
  const [documentType, setDocumentType] = useState("license");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [current, countryList, files] = await Promise.all([
        apiFetch<Profile>("/v1/professionals/me/"),
        apiFetch<Country[]>("/v1/reference/countries/"),
        apiFetch<Document[]>("/v1/professionals/me/documents/"),
      ]);
      setProfile(current);
      setCountries(countryList);
      setDocuments(files);
      const details = current.details ?? {};
      setForm({
        legal_name: current.legal_name, manager_name: current.manager_name, contact_phone: current.contact_phone, contact_email: current.contact_email,
        country: current.country ? String(current.country) : "", region: current.region, city: current.city, address: current.address,
        latitude: current.latitude ?? "", longitude: current.longitude ?? "", description: current.description,
        commercial_name: stringValue(details.commercial_name), license_number: stringValue(details.license_number),
        opening_hours: JSON.stringify(details.opening_hours ?? {}, null, 2), specialty: stringValue(details.specialty),
        registration_number: stringValue(details.registration_number), establishment_name: stringValue(details.establishment_name),
        availability_info: stringValue(details.availability_info), services: listValue(details.services),
        service_areas: JSON.stringify(details.service_areas ?? [], null, 2), delivery_types: listValue(details.delivery_types), transport_modes: listValue(details.transport_modes),
      });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Le profil n’a pas pu être chargé.");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  function updateForm(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function buildDetails(category: CategoryCode) {
    if (category === "pharmacy") return { commercial_name: form.commercial_name, license_number: form.license_number, opening_hours: JSON.parse(form.opening_hours || "{}") };
    if (category === "doctor" || category === "dentist") return { specialty: form.specialty, registration_number: form.registration_number, establishment_name: form.establishment_name, availability_info: form.availability_info };
    if (category === "laboratory") return { license_number: form.license_number, services: form.services.split(",").map((item) => item.trim()).filter(Boolean) };
    return { license_number: form.license_number, service_areas: JSON.parse(form.service_areas || "[]"), delivery_types: form.delivery_types.split(",").map((item) => item.trim()).filter(Boolean), transport_modes: form.transport_modes.split(",").map((item) => item.trim()).filter(Boolean) };
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const details = buildDetails(profile.category);
      const payload = {
        legal_name: form.legal_name, manager_name: form.manager_name, contact_phone: form.contact_phone, contact_email: form.contact_email,
        country: form.country ? Number(form.country) : null, region: form.region, city: form.city, address: form.address,
        latitude: form.latitude || null, longitude: form.longitude || null, description: form.description, details,
      };
      await apiFetch<Profile>("/v1/professionals/me/", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setNotice("Profil enregistré.");
      await load();
    } catch (caught) {
      const detail = caught instanceof ApiError && caught.details ? ` ${JSON.stringify(caught.details)}` : "";
      setError(`${caught instanceof ApiError ? caught.message : "Le profil n’a pas pu être enregistré."}${detail}`);
    } finally { setBusy(false); }
  }

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("Choisissez un fichier à téléverser."); return; }
    const data = new FormData(); data.set("document_type", documentType); data.set("file", file);
    setBusy(true); setError(""); setNotice("");
    try {
      await apiFetch("/v1/professionals/me/documents/", { method: "POST", body: data });
      setFile(null); setNotice("Justificatif téléversé de façon privée."); await load();
    } catch (caught) {
      const detail = caught instanceof ApiError && caught.details ? ` ${JSON.stringify(caught.details)}` : "";
      setError(`${caught instanceof ApiError ? caught.message : "Le document n’a pas pu être téléversé."}${detail}`);
    } finally { setBusy(false); }
  }

  async function submitForReview() {
    setBusy(true); setError(""); setNotice("");
    try { await apiFetch("/v1/professionals/me/submit/", { method: "POST" }); setNotice("Profil soumis à l’administration pour validation."); await load(); }
    catch (caught) { const detail = caught instanceof ApiError && caught.details ? ` ${JSON.stringify(caught.details)}` : ""; setError(`${caught instanceof ApiError ? caught.message : "La soumission a échoué."}${detail}`); }
    finally { setBusy(false); }
  }

  async function deleteDocument(id: number) {
    setBusy(true); setError(""); setNotice("");
    try { await apiFetch(`/v1/professionals/me/documents/${id}/`, { method: "DELETE" }); setNotice("Justificatif supprimé."); await load(); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "Le justificatif n’a pas pu être supprimé."); }
    finally { setBusy(false); }
  }

  const editable = profile && profile.verification_status !== "pending";
  const detailsFields = profile?.category === "pharmacy" ? ["commercial_name", "license_number", "opening_hours"]
    : profile?.category === "doctor" || profile?.category === "dentist" ? ["specialty", "registration_number", "establishment_name", "availability_info"]
    : profile?.category === "laboratory" ? ["license_number", "services"]
    : ["license_number", "service_areas", "delivery_types", "transport_modes"];

  return <main className="min-h-screen bg-slate-50 px-5 py-8 sm:px-8 sm:py-12"><div className="mx-auto max-w-5xl">
    <header className="flex items-center justify-between border-b border-slate-200 pb-5"><div><Link href="/professionnel" className="text-sm font-extrabold text-emerald-800">FANAFODIKO</Link><h1 className="mt-3 text-3xl font-bold">Mon profil professionnel</h1>{profile && <p className="mt-1 text-sm text-slate-600">{profile.category_label} · validation : {profile.verification_status}</p>}</div><Link href="/professionnel" className="text-sm font-semibold text-emerald-800">Retour au tableau de bord</Link></header>
    {error && <p role="alert" className="mt-6 whitespace-pre-wrap rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}{notice && <p role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{notice}</p>}
    {profile && <>
      {!profile.is_complete && <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5"><h2 className="font-semibold text-amber-950">À compléter avant la validation</h2><ul className="mt-2 grid list-inside list-disc gap-1 text-sm text-amber-900 sm:grid-cols-2">{profile.missing_information.map((field) => <li key={field}>{missingLabels[field] ?? field}</li>)}</ul></section>}
      <form onSubmit={saveProfile} className="medical-form mt-6 space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <section><h2 className="text-lg font-semibold">Informations générales</h2><div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">Nom ou raison sociale<input name="legal_name" value={form.legal_name ?? ""} onChange={updateForm} maxLength={180} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Responsable<input name="manager_name" value={form.manager_name ?? ""} onChange={updateForm} maxLength={180} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Téléphone<input name="contact_phone" value={form.contact_phone ?? ""} onChange={updateForm} maxLength={20} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">E-mail de contact<input name="contact_email" type="email" value={form.contact_email ?? ""} onChange={updateForm} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Pays<select name="country" value={form.country ?? ""} onChange={updateForm} disabled={!editable} className={inputClass()}><option value="">Choisir un pays</option>{countries.map((country) => <option key={country.id} value={country.id}>{country.name_fr}</option>)}</select></label>
          <label className="text-sm font-medium">Région<input name="region" value={form.region ?? ""} onChange={updateForm} maxLength={120} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Ville<input name="city" value={form.city ?? ""} onChange={updateForm} maxLength={120} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Adresse<input name="address" value={form.address ?? ""} onChange={updateForm} maxLength={240} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Latitude (facultative)<input name="latitude" type="number" step="0.000001" min="-90" max="90" value={form.latitude ?? ""} onChange={updateForm} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium">Longitude (facultative)<input name="longitude" type="number" step="0.000001" min="-180" max="180" value={form.longitude ?? ""} onChange={updateForm} disabled={!editable} className={inputClass()}/></label>
          <label className="text-sm font-medium sm:col-span-2">Description professionnelle<textarea name="description" value={form.description ?? ""} onChange={updateForm} rows={3} maxLength={4000} disabled={!editable} className={inputClass()}/></label>
        </div></section>

        <section className="border-t border-slate-100 pt-6"><h2 className="text-lg font-semibold">Informations propres à votre activité</h2><div className="mt-4 grid gap-4 sm:grid-cols-2">{detailsFields?.map((field) => <label key={field} className={`text-sm font-medium ${["opening_hours", "services", "service_areas", "delivery_types", "transport_modes", "availability_info"].includes(field) ? "sm:col-span-2" : ""}`}>{detailLabels[field]}{["opening_hours", "service_areas", "availability_info"].includes(field) ? <textarea name={field} value={form[field] ?? ""} onChange={updateForm} rows={field === "availability_info" ? 2 : 4} disabled={!editable} placeholder={field === "opening_hours" ? '{"monday":[{"open":"08:00","close":"17:00"}]}' : field === "service_areas" ? '[{"country_code":"MG","region":"Analamanga","city":"Antananarivo"}]' : ""} className={inputClass()}/> : <input name={field} value={form[field] ?? ""} onChange={updateForm} maxLength={field === "license_number" || field === "registration_number" ? 80 : 180} disabled={!editable} placeholder={field === "services" || field === "delivery_types" || field === "transport_modes" ? "Séparez les valeurs par des virgules" : ""} className={inputClass()}/>}</label>)}</div><p className="mt-3 text-xs text-slate-500">Les horaires et les zones desservies utilisent le format JSON indiqué en exemple.</p></section>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5"><p className="text-xs text-slate-500">Les modifications d’un profil validé demandent une nouvelle validation.</p><button disabled={busy || !editable} className="rounded-xl bg-emerald-700 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Enregistrement…" : "Enregistrer le profil"}</button></div>
      </form>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><div><h2 className="text-lg font-semibold">Documents justificatifs</h2><p className="mt-1 text-sm text-slate-600">PDF, JPEG ou PNG, maximum 10 Mo par document. Les fichiers sont privés.</p></div>
        <form onSubmit={uploadDocument} className="mt-5 grid gap-3 sm:grid-cols-[1fr_2fr_auto] sm:items-end">
          <label className="text-sm font-medium">Type<select value={documentType} onChange={(event) => setDocumentType(event.target.value)} disabled={!editable} className={inputClass()}>{documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="text-sm font-medium">Fichier<input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => setFile(event.target.files?.[0] ?? null)} disabled={!editable} className="mt-1.5 block w-full rounded-xl border border-slate-300 p-2 text-sm"/></label>
          <button disabled={busy || !editable || !file} className="rounded-xl border border-emerald-700 px-4 py-2.5 text-sm font-semibold text-emerald-800 disabled:opacity-50">Téléverser</button>
        </form>
        {documents.length > 0 ? <ul className="mt-5 divide-y divide-slate-100">{documents.map((document) => <li key={document.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><span><span className="font-medium">{document.original_filename}</span><span className="ml-2 text-slate-500">{Math.ceil(document.size_bytes / 1024)} Ko · {document.review_status}</span></span><span className="flex gap-3"><a className="font-semibold text-emerald-800" href={new URL(document.download_url, API_BASE_URL).href}>Télécharger</a><button type="button" disabled={busy || !editable} onClick={() => void deleteDocument(document.id)} className="text-red-700 disabled:opacity-50">Supprimer</button></span></li>)}</ul> : <p className="mt-5 text-sm text-slate-500">Aucun document ajouté.</p>}
      </section>

      {editable && <section className="mt-6 flex flex-col justify-between gap-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 sm:flex-row sm:items-center sm:p-6"><div><h2 className="font-semibold text-emerald-950">Prêt pour l’examen ?</h2><p className="mt-1 text-sm text-emerald-900">La soumission est possible quand toutes les informations et un justificatif sont fournis.</p></div><button type="button" onClick={() => void submitForReview()} disabled={busy || !profile.is_complete} className="shrink-0 rounded-xl bg-emerald-700 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">Soumettre à validation</button></section>}
      {profile.verification_status === "pending" && <p className="mt-6 rounded-xl bg-sky-50 p-4 text-sm text-sky-900">Votre profil est en cours d’examen. Les modifications et suppressions de justificatifs sont temporairement désactivées.</p>}
    </>}
  </div></main>;
}
