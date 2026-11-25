import Link from "next/link";
import { MedicalExperience } from "@/components/MedicalExperience";
import { PublicNavigation } from "@/components/PublicNavigation";
import { PublicFaqList } from "@/components/PublicFaqList";
import { PublicNewsList } from "@/components/PublicNewsList";
import { MarketplaceHomeSection } from "@/components/MarketplacePublic";

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#contenu">Aller au contenu</a>
      <PublicNavigation />
      <main id="contenu">
        <MedicalExperience />
        <MarketplaceHomeSection />

        <section id="about" className="section-wrap scroll-mt-24 bg-[#f3f8fc] py-16 sm:py-20">
          <div className="mx-auto grid max-w-7xl gap-10 px-5 sm:px-8 lg:grid-cols-[.8fr_1.2fr] lg:items-center">
            <div><p className="section-kicker">À propos de FANAFODIKO</p><h2 className="section-title">La santé plus proche, avec une expérience qui vous ressemble.</h2></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <article className="info-card"><span className="info-card-icon">♡</span><h3>Pour les patients</h3><p>Un accès clair aux informations et aux services de santé au fur et à mesure de leur disponibilité.</p></article>
              <article className="info-card"><span className="info-card-icon info-card-icon-teal">✚</span><h3>Pour les professionnels</h3><p>Un espace dédié pour créer votre profil, transmettre vos justificatifs et suivre votre dossier.</p><Link href="/professionnel/inscription" className="text-link mt-4">Découvrir l’espace professionnel <span aria-hidden="true">→</span></Link></article>
            </div>
          </div>
        </section>

        <section id="faq" className="section-wrap scroll-mt-24 bg-white py-16 sm:py-20">
          <div className="mx-auto max-w-4xl px-5 sm:px-8">
            <div className="mb-8 text-center"><p className="section-kicker">FAQ</p><h2 className="section-title">Quelques réponses utiles</h2></div>
            <PublicFaqList fallback={[["Comment rejoindre FANAFODIKO en tant que professionnel ?", "Vous pouvez créer un compte professionnel, compléter votre profil et transmettre un justificatif depuis /professionnel/inscription."], ["Les profils de professionnels sont-ils déjà consultables ?", "L’annuaire public n’est pas encore ouvert."], ["L’inscription patient est-elle disponible ?", "Oui, vous pouvez créer un compte patient et mettre à jour vos informations personnelles. Les rendez-vous et téléconsultations ne sont pas encore proposés."]]}/>
          </div>
        </section>

        <section id="espace-patient" className="scroll-mt-24 bg-gradient-to-r from-blue-800 via-blue-700 to-teal-700 px-5 py-12 text-white sm:px-8 sm:py-14">
          <div className="mx-auto flex max-w-7xl flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-sm font-semibold text-teal-200">Espace patient</p><h2 className="mt-1 text-2xl font-bold tracking-tight">Gérez vos informations personnelles.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-blue-100">Créez votre compte pour renseigner et mettre à jour vos coordonnées.</p></div>
            <div className="flex flex-wrap gap-3"><Link href="/patient/inscription" className="inline-flex min-h-11 items-center rounded-xl bg-white px-4 py-2 text-sm font-semibold text-blue-900 hover:bg-blue-50">Créer un compte patient</Link><Link href="/patient/connexion" className="inline-flex min-h-11 items-center rounded-xl border border-white/50 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10">Connexion patient</Link></div>
          </div>
        </section>

        <section id="actualites" className="section-wrap scroll-mt-24 bg-[#f3f8fc] py-16 sm:py-20">
          <div className="mx-auto max-w-7xl px-5 sm:px-8">
            <p className="section-kicker">Actualités</p><h2 className="section-title">Les nouvelles de FANAFODIKO</h2>
            <PublicNewsList />
          </div>
        </section>

        <section id="contact" className="scroll-mt-24 bg-white py-14">
          <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 sm:px-8 md:flex-row md:items-center md:justify-between">
            <div><p className="section-kicker">Contact</p><h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">Une question sur l’espace professionnel ?</h2><p className="mt-2 text-sm text-slate-600">Consultez le parcours d’inscription ou connectez-vous à votre espace professionnel.</p></div>
            <div className="flex flex-wrap gap-3"><Link href="/professionnel/inscription" className="button-primary">Rejoindre FANAFODIKO</Link><Link href="/professionnel/connexion" className="button-outline">Connexion professionnelle</Link></div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-slate-950 text-slate-300">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-8 sm:px-8 md:flex-row md:items-center md:justify-between">
          <Link href="/" className="text-sm font-extrabold tracking-wide text-white">FANAFODIKO<span className="text-teal-400">.</span></Link>
          <nav aria-label="Liens de pied de page" className="flex flex-wrap gap-x-5 gap-y-2 text-xs"><Link href="/a-propos" className="footer-link">À propos</Link><Link href="/faq" className="footer-link">FAQ</Link><Link href="/contact" className="footer-link">Contact</Link><Link href="/actualites" className="footer-link">Actualités</Link><Link href="/conditions" className="footer-link">Conditions d’utilisation</Link><Link href="/confidentialite" className="footer-link">Confidentialité</Link><Link href="/professionnel" className="footer-link">Espace professionnel</Link></nav>
          <p className="text-xs text-slate-400">© 2026 FANAFODIKO · Votre santé, plus proche.</p>
        </div>
      </footer>
    </>
  );
}
