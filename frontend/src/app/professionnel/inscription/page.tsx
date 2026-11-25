"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { registrationFieldErrors } from "@/lib/registration-errors";

type Category = { code: string; label: string };

export default function ProfessionalRegistrationPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<ReturnType<typeof registrationFieldErrors>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => { void apiFetch<Category[]>("/v1/professionals/categories/").then(setCategories).catch(() => setError("Les catégories n’ont pas pu être chargées.")); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFieldErrors({});
    setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      await apiFetch("/v1/auth/csrf/");
      await apiFetch("/v1/auth/register/", { method: "POST", body: JSON.stringify(Object.fromEntries(data)), headers: { "Content-Type": "application/json" } });
      router.push("/professionnel");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(registrationFieldErrors(caught.details));
      } else {
        setError("Le compte n’a pas pu être créé.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f8f6] px-5 py-10 sm:py-16">
      <div className="mx-auto max-w-xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9">
        <Link href="/" className="text-sm font-extrabold tracking-wide text-emerald-800">FANAFODIKO</Link>
        <p className="mt-8 text-sm font-semibold text-emerald-700">Espace professionnel</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">Créer mon compte</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">Votre profil sera enregistré en brouillon. Vous pourrez le compléter avant de le soumettre à l’administration.</p>

        <form onSubmit={submit} className="medical-form mt-7 space-y-4">
          <label className="block text-sm font-medium text-slate-800">Catégorie professionnelle<select name="category" required defaultValue="" aria-invalid={Boolean(fieldErrors.category)} aria-describedby={fieldErrors.category ? "category-error" : undefined} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 outline-none focus-visible:border-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-200"><option className="bg-white text-slate-900" value="" disabled>Choisir une catégorie</option>{categories.map((category) => <option className="bg-white text-slate-900" key={category.code} value={category.code}>{category.label}</option>)}</select>{fieldErrors.category && <span id="category-error" className="mt-1 block text-xs text-red-700">{fieldErrors.category}</span>}</label>
          <label className="block text-sm font-medium text-slate-800">Nom ou raison sociale<input name="legal_name" required maxLength={180} autoComplete="organization" aria-invalid={Boolean(fieldErrors.legal_name)} aria-describedby={fieldErrors.legal_name ? "legal-name-error" : undefined} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 placeholder:text-slate-500 selection:bg-emerald-200 selection:text-emerald-950 outline-none focus-visible:border-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-200"/>{fieldErrors.legal_name && <span id="legal-name-error" className="mt-1 block text-xs text-red-700">{fieldErrors.legal_name}</span>}</label>
          <label className="block text-sm font-medium text-slate-800">Adresse e-mail<input name="email" type="email" required autoComplete="email" aria-invalid={Boolean(fieldErrors.email)} aria-describedby={fieldErrors.email ? "email-error" : undefined} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 placeholder:text-slate-500 selection:bg-emerald-200 selection:text-emerald-950 outline-none focus-visible:border-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-200"/>{fieldErrors.email && <span id="email-error" className="mt-1 block text-xs text-red-700">{fieldErrors.email}</span>}</label>
          <label className="block text-sm font-medium text-slate-800">Téléphone de contact <span className="font-normal text-slate-500">(facultatif)</span><input name="contact_phone" type="tel" autoComplete="tel" maxLength={20} aria-invalid={Boolean(fieldErrors.contact_phone)} aria-describedby={fieldErrors.contact_phone ? "phone-error" : undefined} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 placeholder:text-slate-500 selection:bg-emerald-200 selection:text-emerald-950 outline-none focus-visible:border-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-200"/>{fieldErrors.contact_phone && <span id="phone-error" className="mt-1 block text-xs text-red-700">{fieldErrors.contact_phone}</span>}</label>
          <label className="block text-sm font-medium text-slate-800">Mot de passe<input name="password" type="password" required minLength={8} autoComplete="new-password" aria-invalid={Boolean(fieldErrors.password)} aria-describedby={fieldErrors.password ? "password-error" : undefined} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 placeholder:text-slate-500 selection:bg-emerald-200 selection:text-emerald-950 outline-none focus-visible:border-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-200"/>{fieldErrors.password && <span id="password-error" className="mt-1 block text-xs text-red-700">{fieldErrors.password}</span>}<span className="mt-1 block text-xs font-normal text-slate-500">Choisissez un mot de passe robuste; les règles Django s’appliquent.</span></label>
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}
          <button disabled={busy || categories.length === 0} className="w-full rounded-xl bg-emerald-700 px-4 py-3 font-semibold text-white hover:bg-emerald-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-60">{busy ? "Création du compte…" : "Créer mon compte professionnel"}</button>
        </form>
        <p className="mt-6 text-sm text-slate-600">Vous avez déjà un compte ? <Link className="font-semibold text-emerald-800" href="/professionnel/connexion">Se connecter</Link></p>
      </div>
    </main>
  );
}
