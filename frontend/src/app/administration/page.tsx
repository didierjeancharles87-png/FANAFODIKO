"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import { AdministrationContent } from "@/components/AdministrationContent";
import { AdminOperations } from "@/components/AdminOperations";

const djangoAdminUrl = process.env.NEXT_PUBLIC_DJANGO_ADMIN_URL ?? "http://localhost:8000/admin/";

type AdminDashboard = {
  users: { total: number; active: number; suspended: number; closed: number; disabled: number };
  professional_verifications: { pending: number; approved: number; rejected: number };
};

export default function AdministrationDashboard() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<AdminDashboard>("/v1/admin/dashboard/");
      setDashboard(data);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Le tableau de bord n’a pas pu être chargé.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function signOut() {
    try {
      await apiFetch("/v1/auth/csrf/");
      await apiFetch("/v1/auth/logout/", { method: "POST" });
      router.replace("/"); router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "La déconnexion n’a pas abouti.");
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col justify-between gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-end">
          <div>
            <Link href="/" className="text-sm font-bold tracking-wide text-emerald-800">FANAFODIKO</Link>
            <p className="mt-5 text-sm font-semibold text-emerald-700">Administration centrale</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Vue d’ensemble</h1>
            <p className="mt-2 text-sm text-slate-600">Indicateurs calculés à partir des comptes et demandes enregistrés.</p>
          </div>
          <div className="flex gap-3">
            <button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-100 disabled:opacity-60">Actualiser</button>
            <a href={djangoAdminUrl} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800">Gérer les données</a>
            <button type="button" onClick={() => void signOut()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">Se déconnecter</button>
          </div>
        </header>

        {error && <div role="alert" className="mt-8 rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950"><p className="font-semibold">Accès au tableau de bord impossible</p><p className="mt-1">{error}</p><p className="mt-2">Connectez-vous avec un compte administrateur actif sur le site Django, puis réessayez.</p></div>}
        {loading && !dashboard && <p className="mt-8 text-sm text-slate-600" role="status">Chargement des indicateurs…</p>}

        {dashboard && <section aria-label="Indicateurs" className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { label: "Comptes", value: dashboard.users.total },
            { label: "Comptes actifs", value: dashboard.users.active },
            { label: "Comptes suspendus", value: dashboard.users.suspended },
            { label: "Accès désactivés", value: dashboard.users.disabled },
            { label: "Validations en attente", value: dashboard.professional_verifications.pending },
            { label: "Professionnels validés", value: dashboard.professional_verifications.approved },
            { label: "Demandes refusées", value: dashboard.professional_verifications.rejected },
          ].map((metric) => <article key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-sm font-medium text-slate-600">{metric.label}</p><p className="mt-3 text-4xl font-bold tabular-nums">{metric.value}</p></article>)}
        </section>}
        {dashboard && <AdminOperations />}
        {dashboard && <AdministrationContent />}
      </div>
    </main>
  );
}
