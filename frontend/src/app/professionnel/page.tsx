"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";

type Profile = {
  id: number;
  category_label: string;
  legal_name: string;
  verification_status: "draft" | "pending" | "approved" | "rejected";
  is_complete: boolean;
  missing_information: string[];
};
type Session = { email: string; account_status: string; professional_profile_id: number | null };

const fieldLabels: Record<string, string> = {
  legal_name: "Nom ou raison sociale", manager_name: "Responsable", contact_phone: "Téléphone", contact_email: "E-mail de contact",
  country: "Pays", region: "Région", city: "Ville", address: "Adresse", commercial_name: "Nom commercial", opening_hours: "Horaires d’ouverture",
  specialty: "Spécialité", establishment_name: "Établissement ou cabinet", services: "Services ou analyses proposés",
  service_areas: "Zones desservies", delivery_types: "Types de livraison", transport_modes: "Moyens de transport", supporting_document: "Au moins un justificatif",
};
const statusLabels = { draft: "Brouillon", pending: "En cours de validation", approved: "Profil validé", rejected: "À compléter après examen" };

export default function ProfessionalDashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [currentSession, currentProfile] = await Promise.all([
        apiFetch<Session>("/v1/auth/me/"),
        apiFetch<Profile>("/v1/professionals/me/"),
      ]);
      setSession(currentSession);
      setProfile(currentProfile);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Le tableau de bord n’a pas pu être chargé.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function signOut() {
    try {
      await apiFetch("/v1/auth/logout/", { method: "POST" });
    } finally {
      router.push("/professionnel/connexion");
    }
  }

  return <main className="min-h-screen bg-slate-50 px-5 py-10 sm:px-8"><div className="mx-auto max-w-5xl">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5"><div><Link href="/" className="text-sm font-extrabold text-emerald-800">FANAFODIKO</Link><h1 className="mt-3 text-3xl font-bold text-slate-900">Mon espace professionnel</h1>{session && <p className="mt-1 text-sm text-slate-600">{session.email}</p>}</div>{session && <button onClick={() => void signOut()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold">Se déconnecter</button>}</header>
    {loading && <p role="status" className="mt-8 text-sm text-slate-600">Chargement du profil…</p>}
    {!loading && error && <div role="alert" className="mt-8 rounded-2xl border border-amber-300 bg-amber-50 p-6"><p className="font-semibold text-amber-950">Espace non accessible</p><p className="mt-2 text-sm text-amber-900">{error}</p><div className="mt-5 flex flex-wrap gap-3"><Link href="/professionnel/connexion" className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white">Se connecter</Link><Link href="/professionnel/inscription" className="rounded-lg border border-emerald-700 px-4 py-2 text-sm font-semibold text-emerald-800">Créer un compte</Link></div></div>}
    {profile && <><section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-semibold text-emerald-700">{profile.category_label}</p><h2 className="mt-1 text-2xl font-bold">{profile.legal_name}</h2><p className="mt-3 text-sm text-slate-600">État du profil : <span className="font-semibold text-slate-900">{statusLabels[profile.verification_status]}</span></p></div><Link href="/professionnel/profil" className="rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800">{profile.verification_status === "draft" || profile.verification_status === "rejected" ? "Compléter mon profil" : "Consulter mon profil"}</Link></div>
      {!profile.is_complete && <div className="mt-6 rounded-xl bg-amber-50 p-4"><h3 className="font-semibold text-amber-950">Informations manquantes</h3><ul className="mt-2 list-inside list-disc text-sm text-amber-900">{profile.missing_information.map((field) => <li key={field}>{fieldLabels[field] ?? field}</li>)}</ul></div>}
      {profile.verification_status === "draft" || profile.verification_status === "rejected" ? <p className="mt-5 text-sm text-slate-600">Complétez les informations et ajoutez un justificatif pour pouvoir demander la validation administrative.</p> : null}
    </section><section className="mt-5 rounded-2xl border border-slate-200 bg-white p-6"><h3 className="font-semibold">Étapes suivantes</h3><ol className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-3"><li>1. Compléter les informations professionnelles</li><li>2. Ajouter les documents justificatifs</li><li>3. Soumettre à l’administration</li></ol></section></>}
  </div></main>;
}
