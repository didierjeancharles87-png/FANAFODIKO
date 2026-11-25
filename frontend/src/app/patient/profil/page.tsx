"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { PublicNavigation } from "@/components/PublicNavigation";

type PatientProfile = { email: string; first_name: string; last_name: string; phone_number: string; country: number | null };
type Country = { id: number; name_fr: string };

export default function PatientProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [countries, setCountries] = useState<Country[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    void apiFetch<PatientProfile>("/v1/accounts/patient/profile/")
      .then(setProfile)
      .catch((caught) => setError(caught instanceof ApiError && caught.status === 403 ? "Connectez-vous avec un compte patient pour consulter cette page." : "Le profil patient n’a pas pu être chargé."));
    void apiFetch<Country[]>("/v1/reference/countries/").then(setCountries).catch(() => undefined);
  }, []);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!profile) return;
    setBusy(true); setError(""); setNotice("");
    const form = new FormData(event.currentTarget);
    const countryValue = String(form.get("country") ?? "");
    const payload = { first_name: String(form.get("first_name") ?? ""), last_name: String(form.get("last_name") ?? ""), phone_number: String(form.get("phone_number") ?? ""), country: countryValue ? Number(countryValue) : null };
    try {
      await apiFetch("/v1/auth/csrf/");
      const updated = await apiFetch<PatientProfile>("/v1/accounts/patient/profile/", { method: "PATCH", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } });
      setProfile(updated); setNotice("Vos informations ont été mises à jour.");
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "La mise à jour a échoué."); }
    finally { setBusy(false); }
  }
  async function signOut() {
    setError("");
    try { await apiFetch("/v1/auth/logout/", { method: "POST" }); router.replace("/"); router.refresh(); }
    catch { setError("La déconnexion n’a pas abouti. Réessayez."); }
  }
  return <><PublicNavigation /><main className="min-h-screen bg-[#f4f9fc] px-5 py-10 sm:py-16"><div className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"><Link href="/" className="text-sm font-extrabold tracking-wide text-blue-800">FANAFODIKO</Link><header className="mt-8 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold text-teal-700">Espace patient</p><h1 className="mt-2 text-3xl font-bold">Mes informations</h1></div><button type="button" onClick={() => void signOut()} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Se déconnecter</button></header>
    {profile ? <form onSubmit={save} className="medical-form mt-7 space-y-4"><label className="block text-sm font-medium">Adresse e-mail<input value={profile.email} readOnly className="mt-1.5 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-slate-600"/></label><label className="block text-sm font-medium">Prénom<input name="first_name" defaultValue={profile.first_name} maxLength={150} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3"/></label><label className="block text-sm font-medium">Nom<input name="last_name" defaultValue={profile.last_name} maxLength={150} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3"/></label><label className="block text-sm font-medium">Téléphone<input name="phone_number" type="tel" defaultValue={profile.phone_number} maxLength={20} autoComplete="tel" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3"/></label><label className="block text-sm font-medium">Pays<select name="country" defaultValue={profile.country ?? ""} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-3"><option value="">Non renseigné</option>{countries.map((country) => <option key={country.id} value={country.id}>{country.name_fr}</option>)}</select></label>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}{notice && <p role="status" className="rounded-xl bg-teal-50 p-3 text-sm text-teal-900">{notice}</p>}<button disabled={busy} className="w-full rounded-xl bg-blue-800 px-4 py-3 font-semibold text-white hover:bg-blue-900 disabled:opacity-60">{busy ? "Enregistrement…" : "Enregistrer mes informations"}</button></form> : <div className="mt-8">{error ? <p role="alert" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">{error}</p> : <p role="status" className="text-sm text-slate-600">Chargement du profil…</p>}<Link href="/patient/connexion" className="mt-4 inline-block text-sm font-semibold text-blue-800">Connexion patient</Link></div>}
    </div></main></>;
}
