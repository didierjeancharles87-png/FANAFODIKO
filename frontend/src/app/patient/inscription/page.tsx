"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { PublicNavigation } from "@/components/PublicNavigation";
import { countryListFromApi, countryLoadErrorMessage } from "@/lib/country-list.mjs";

type Country = { id: number; name_fr: string; code_alpha2: string };

export default function PatientRegistrationPage() {
  const router = useRouter();
  const [countries, setCountries] = useState<Country[]>([]);
  const [countriesLoaded, setCountriesLoaded] = useState(false);
  const [countriesError, setCountriesError] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>(Object.create(null));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void apiFetch<unknown>("/v1/reference/countries/")
      .then((response) => countryListFromApi(response) as Country[])
      .then((items) => { if (active) { setCountries(items); setCountriesLoaded(true); } })
      .catch((caught: unknown) => { if (active) { setCountriesError(countryLoadErrorMessage(caught)); setCountriesLoaded(true); } });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setFieldErrors(Object.create(null)); setBusy(true);
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData);
    if (!payload.country) delete payload.country;
    try {
      await apiFetch("/v1/auth/csrf/");
      await apiFetch("/v1/auth/register-patient/", { method: "POST", body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } });
      router.replace("/patient/profil");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        const details = caught.details as Record<string, unknown> | undefined;
        if (details && typeof details === "object") {
          const mapped: Record<string, string> = Object.create(null);
          for (const [key, value] of Object.entries(details)) mapped[key] = Array.isArray(value) ? value.map(String).join(" ") : String(value);
          setFieldErrors(mapped);
        }
      } else setError("Le compte patient n’a pas pu être créé.");
    } finally { setBusy(false); }
  }

  return <><PublicNavigation /><main className="min-h-screen bg-[#f4f9fc] px-5 py-10 sm:py-16"><div className="mx-auto max-w-xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"><Link href="/" className="text-sm font-extrabold tracking-wide text-blue-800">FANAFODIKO</Link><p className="mt-8 text-sm font-semibold text-teal-700">Espace patient</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Créer un compte patient</h1><p className="mt-3 text-sm leading-6 text-slate-600">Le compte permet de gérer vos informations personnelles. Aucun service de rendez-vous ou de téléconsultation n’est actuellement proposé.</p>
    <form onSubmit={submit} className="medical-form mt-7 space-y-4">
      <Field name="first_name" label="Prénom" required autoComplete="given-name" error={fieldErrors.first_name} />
      <Field name="last_name" label="Nom" required autoComplete="family-name" error={fieldErrors.last_name} />
      <Field name="email" label="Adresse e-mail" type="email" required autoComplete="email" error={fieldErrors.email} />
      <Field name="phone_number" label="Téléphone (facultatif)" type="tel" autoComplete="tel" error={fieldErrors.phone_number} />
      <label className="medical-form-label">Pays (facultatif)<select name="country" defaultValue="" disabled={!countriesLoaded || Boolean(countriesError)} className="medical-form-control mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3"><option value="">{countriesLoaded ? "Choisir un pays" : "Chargement des pays…"}</option>{countries.map((country) => <option key={country.id} value={country.id}>{country.name_fr}</option>)}</select>{countriesError && <span role="alert" className="mt-1 block text-xs text-red-700">{countriesError}</span>}{countriesLoaded && !countriesError && countries.length === 0 && <span className="mt-1 block text-xs text-slate-600">Aucun pays actif n’est disponible pour le moment.</span>}{fieldErrors.country && <span className="mt-1 block text-xs text-red-700">{fieldErrors.country}</span>}</label>
      <Field name="password" label="Mot de passe" type="password" required autoComplete="new-password" error={fieldErrors.password} helper="Les règles de robustesse Django s’appliquent." />
      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <button disabled={busy} className="w-full rounded-xl bg-blue-800 px-4 py-3 font-semibold text-white hover:bg-blue-900 disabled:opacity-60">{busy ? "Création du compte…" : "Créer mon compte patient"}</button>
    </form><p className="mt-6 text-sm text-slate-600">Vous avez déjà un compte ? <Link href="/patient/connexion" className="font-semibold text-blue-800">Se connecter</Link></p></div></main></>;
}

function Field({ name, label, type = "text", required = false, autoComplete, error, helper }: { name: string; label: string; type?: string; required?: boolean; autoComplete?: string; error?: string; helper?: string }) {
  const errorId = `${name}-error`;
  return <label className="medical-form-label">{label}<input name={name} type={type} required={required} maxLength={name === "phone_number" ? 20 : 150} autoComplete={autoComplete} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} className="medical-form-control mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3 outline-none focus-visible:ring-2 focus-visible:ring-teal-300"/>{error && <span id={errorId} className="mt-1 block text-xs text-red-700">{error}</span>}{helper && <span className="mt-1 block text-xs font-normal text-slate-600">{helper}</span>}</label>;
}
