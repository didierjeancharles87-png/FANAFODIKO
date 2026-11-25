"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Session = {
  email: string;
  roles: string[];
  professional_profile_id: number | null;
};

const navigation = [
  ["Accueil", "/"],
  ["À propos", "/a-propos"],
  ["FAQ", "/faq"],
  ["Contact", "/contact"],
  ["Actualités", "/actualites"],
  ["Catalogue", "/medicaments"],
  ["Promotions", "/promotions"],
  ["Recherche", "/recherche"],
] as const;

export function PublicNavigation() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isPartner, setIsPartner] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);

  useEffect(() => {
    let active = true;
    void apiFetch<Session>("/v1/auth/me/")
      .then(async (current) => {
        let canAccessAdmin = false;
        let canAccessPartner = false;
        try {
          await apiFetch("/v1/admin/dashboard/");
          canAccessAdmin = true;
        } catch {
          // The API permission check keeps the administration link role-safe.
        }
        try {
          await apiFetch("/v1/partner/dashboard/");
          canAccessPartner = true;
        } catch {
          // The partner link is shown only when the API confirms a seller assignment.
        }
        if (active) {
          setSession(current);
          setIsAdmin(canAccessAdmin);
          setIsPartner(canAccessPartner);
        }
      })
      .catch(() => {
        if (active) setSession(null);
      })
      .finally(() => {
        if (active) setSessionChecked(true);
      });
    return () => { active = false; };
  }, []);

  async function signOut() {
    try {
      await apiFetch("/v1/auth/logout/", { method: "POST" });
    } catch {
      // Clear the local navigation state even when the session has expired.
    }
    setSession(null);
    setIsAdmin(false);
    setIsPartner(false);
    setMobileOpen(false);
    router.refresh();
  }

  function closeMenu() {
    setMobileOpen(false);
  }

  const roleLabel = isAdmin
    ? "Administration"
    : isPartner
      ? "Espace partenaire"
      : session?.professional_profile_id
        ? "Espace professionnel"
        : session?.roles.includes("patient")
          ? "Espace patient"
          : "Mon compte";

  const accountHref = isAdmin
    ? "/administration"
    : isPartner
      ? "/partenaire"
      : session?.professional_profile_id
        ? "/professionnel"
        : session?.roles.includes("patient")
          ? "/patient/profil"
          : "#espace-patient";

  return (
    <header className="site-header sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 backdrop-blur-lg" onKeyDown={(event) => { if (event.key === "Escape") closeMenu(); }}>
      <div className="mx-auto flex min-h-[76px] max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" onClick={closeMenu} className="flex shrink-0 items-center gap-2.5" aria-label="FANAFODIKO, accueil">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-700 to-teal-500 text-xl font-bold text-white shadow-sm" aria-hidden="true">F</span>
          <span className="text-lg font-extrabold tracking-tight text-slate-900 sm:text-xl">FANAFODIKO<span className="text-teal-500">.</span></span>
        </Link>

        <nav aria-label="Navigation principale" className="hidden items-center gap-5 xl:flex">
          {navigation.map(([label, href]) => <Link key={label} href={href} className="nav-link">{label}</Link>)}
        </nav>

        <div className="hidden items-center gap-2 xl:flex">
          {session ? (
            <div className="flex items-center gap-2">
              {isAdmin && <Link href="/administration" className="nav-secondary">Administration</Link>}
              {isPartner && <Link href="/partenaire" className="nav-secondary">Espace partenaire</Link>}
              {session.professional_profile_id && <Link href="/professionnel" className="nav-secondary">Espace professionnel</Link>}
              {!session.professional_profile_id && session.roles.includes("patient") && <>
                <Link href="/panier" className="nav-secondary">Panier</Link>
                <Link href="/commandes" className="nav-secondary">Réservations</Link>
                <Link href="/patient/profil" className="nav-secondary">Espace patient</Link>
              </>}
              <details className="relative">
                <summary className="user-menu-trigger">
                  <UserIcon />
                  <span className="max-w-36 truncate">{session.email}</span>
                  <span className="sr-only">Ouvrir le menu du compte</span>
                </summary>
                <div className="absolute right-0 top-full mt-2 w-60 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-900/10">
                  <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{roleLabel}</p>
                  <Link href={accountHref} className="account-menu-item" onClick={closeMenu}>{roleLabel}</Link>
                  {session.professional_profile_id && <Link href="/professionnel/profil" className="account-menu-item">Profil professionnel</Link>}
                  {!session.professional_profile_id && session.roles.includes("patient") && <Link href="/patient/profil" className="account-menu-item">Profil patient</Link>}
                  <button type="button" onClick={() => void signOut()} className="account-menu-item w-full text-left text-rose-700">Se déconnecter</button>
                </div>
              </details>
            </div>
          ) : (
            <>
              <Link href="/professionnel" className="nav-secondary">Espace professionnel</Link>
              <Link href="/patient/inscription" className="nav-secondary">Inscription patient</Link>
              <Link href="/professionnel/connexion" className="login-button"><UserIcon />Se connecter</Link>
            </>
          )}
          {!session && sessionChecked && <span className="sr-only">Vous êtes déconnecté.</span>}
        </div>

        <button
          type="button"
          className="mobile-menu-button xl:hidden"
          aria-label={mobileOpen ? "Fermer le menu" : "Ouvrir le menu"}
          aria-expanded={mobileOpen}
          aria-controls="mobile-navigation"
          onClick={() => setMobileOpen((open) => !open)}
          onKeyDown={(event) => { if (event.key === "Escape") closeMenu(); }}
        >
          {mobileOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>

      {mobileOpen && (
        <div id="mobile-navigation" className="mobile-navigation xl:hidden">
          <nav aria-label="Navigation mobile" className="mx-auto max-w-7xl px-4 pb-5 sm:px-6">
            <div className="grid gap-1 border-b border-slate-100 pb-4">
              {navigation.map(([label, href]) => <Link key={label} href={href} className="mobile-nav-link" onClick={closeMenu}>{label}</Link>)}
            </div>
            <div className="grid gap-2 pt-4">
              {session ? (
                <>
                  <p className="px-3 text-xs font-medium text-slate-500">{session.email} · {roleLabel}</p>
                  {isAdmin && <Link href="/administration" className="mobile-nav-link" onClick={closeMenu}>Administration</Link>}
                  {isPartner && <Link href="/partenaire" className="mobile-nav-link" onClick={closeMenu}>Espace partenaire</Link>}
                  {session.professional_profile_id && <Link href="/professionnel" className="mobile-nav-link" onClick={closeMenu}>Espace professionnel</Link>}
                  {session.professional_profile_id && <Link href="/professionnel/profil" className="mobile-nav-link" onClick={closeMenu}>Profil professionnel</Link>}
                  {!session.professional_profile_id && session.roles.includes("patient") && <>
                    <Link href="/panier" className="mobile-nav-link" onClick={closeMenu}>Panier</Link>
                    <Link href="/commandes" className="mobile-nav-link" onClick={closeMenu}>Mes réservations</Link>
                    <Link href="/patient/profil" className="mobile-nav-link" onClick={closeMenu}>Profil patient</Link>
                  </>}
                  <button type="button" className="mobile-nav-link text-left text-rose-700" onClick={() => void signOut()}>Se déconnecter</button>
                </>
              ) : (
                <>
                  <Link href="/professionnel" className="mobile-nav-link" onClick={closeMenu}>Espace professionnel</Link>
                  <Link href="/patient/inscription" className="mobile-nav-link" onClick={closeMenu}>Inscription patient</Link>
                  <Link href="/patient/connexion" className="mobile-nav-link" onClick={closeMenu}>Connexion patient</Link>
                  <Link href="/professionnel/connexion" className="login-button justify-center" onClick={closeMenu}><UserIcon />Se connecter</Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}

function UserIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="8" r="3.3"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0" strokeLinecap="round"/></svg>;
}

function MenuIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>;
}

function CloseIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg>;
}
