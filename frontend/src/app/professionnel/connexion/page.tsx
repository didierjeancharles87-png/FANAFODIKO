"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "@/lib/api";

type AuthSession = { roles: string[]; professional_profile_id: number | null };

export default function ProfessionalLoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      await apiFetch("/v1/auth/csrf/");
      const session = await apiFetch<AuthSession>("/v1/auth/login/", { method: "POST", body: JSON.stringify(Object.fromEntries(data)), headers: { "Content-Type": "application/json" } });
      if (session.professional_profile_id) router.push("/professionnel");
      else if (session.roles.includes("patient")) router.push("/patient/profil");
      else {
        try { await apiFetch("/v1/admin/dashboard/"); router.push("/administration"); }
        catch { setError("Ce compte ne possède pas d’espace patient, professionnel ou administrateur actif."); await apiFetch("/v1/auth/logout/", { method: "POST" }); }
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "La connexion a échoué.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="min-h-screen bg-[#f7f8f6] px-5 py-10 sm:py-16"><div className="mx-auto max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9"><Link href="/" className="text-sm font-extrabold tracking-wide text-emerald-800">FANAFODIKO</Link><p className="mt-8 text-sm font-semibold text-emerald-700">Espace professionnel</p><h1 className="mt-2 text-3xl font-bold">Connexion</h1><form onSubmit={submit} className="medical-form mt-7 space-y-4"><label className="block text-sm font-medium">Adresse e-mail<input name="email" type="email" required autoComplete="email" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3"/></label><label className="block text-sm font-medium">Mot de passe<input name="password" type="password" required autoComplete="current-password" className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-3"/></label>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}<button disabled={busy} className="w-full rounded-xl bg-emerald-700 px-4 py-3 font-semibold text-white hover:bg-emerald-800 disabled:opacity-60">{busy ? "Connexion…" : "Se connecter"}</button></form><p className="mt-6 text-sm text-slate-600">Nouveau sur FANAFODIKO ? <Link href="/professionnel/inscription" className="font-semibold text-emerald-800">Créer un compte</Link></p></div></main>;
}
