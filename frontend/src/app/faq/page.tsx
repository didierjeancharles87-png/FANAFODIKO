import Link from "next/link";
import { PageHeading, PublicPageLayout } from "@/components/PublicPageLayout";
import { PublicFaqList } from "@/components/PublicFaqList";

const items: [string, string][] = [
  ["FANAFODIKO est-il déjà un annuaire public ?", "Non. L’annuaire public n’est pas encore disponible. Aucun professionnel ou établissement n’est affiché comme partenaire à ce stade."],
  ["Comment un professionnel peut-il s’inscrire ?", "Le parcours professionnel est accessible depuis la page Espace professionnel. Le dossier peut demander des informations et justificatifs pour examen."],
  ["L’inscription patient est-elle ouverte ?", "Oui. Vous pouvez créer un compte patient et mettre à jour vos informations personnelles. Les rendez-vous et téléconsultations ne sont pas encore proposés."],
  ["Puis-je prendre rendez-vous ou consulter un médecin en ligne ?", "La prise de rendez-vous et la téléconsultation ne sont pas proposées actuellement. Le carrousel présente ces sujets à titre illustratif."],
  ["Un laboratoire peut-il effectuer un prélèvement à domicile ?", "Certains laboratoires peuvent proposer ce service. Il faut vérifier directement avec le laboratoire concerné, car la disponibilité dépend de son offre et de la zone desservie."],
  ["Quels prélèvements peuvent être réalisés à domicile ?", "Selon le laboratoire, l’examen demandé et les conditions de prélèvement, il peut s’agir d’un prélèvement sanguin, d’un recueil d’urine ou d’autres prélèvements biologiques. Le laboratoire indique les consignes avant l’examen."],
  ["Comment demander un prélèvement à domicile ?", "Contactez le laboratoire choisi pour confirmer qu’il effectue les prélèvements à domicile, vérifier la zone, les horaires, la préparation requise et les modalités de remise des résultats. FANAFODIKO ne prend pas encore de réservation."],
  ["Comment mes informations sont-elles utilisées ?", "Les données nécessaires à un compte ou à un dossier professionnel sont traitées par les fonctions du service. Les justificatifs professionnels sont conservés dans un espace privé et leur téléchargement est limité aux personnes autorisées. Consultez la page Confidentialité pour le détail connu et ses limites."],
  ["Comment contacter l’équipe ?", "La page Contact présente un formulaire en préparation. Il n’envoie pas encore de message."],
];

export default function FaqPage() {
  return <PublicPageLayout><PageHeading kicker="FAQ" title="Questions fréquentes" intro="Informations sur les fonctionnalités actuellement disponibles et les services encore en préparation." /><section className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14"><PublicFaqList fallback={items} /><p className="mt-8 text-sm text-slate-600">Pour les professionnels, consultez la page <Link href="/professionnel" className="text-link">Espace professionnel</Link>.</p></section></PublicPageLayout>;
}
