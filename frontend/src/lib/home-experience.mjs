export const medicalSlides = [
  {
    id: "teleconsultation",
    eyebrow: "TÉLÉCONSULTATION",
    title: "Un accompagnement médical plus proche.",
    description: "La téléconsultation et l’accompagnement médical font partie des thèmes présentés sur FANAFODIKO. Les services disponibles seront précisés lorsque l’offre sera ouverte.",
    actionLabel: "Découvrir les médecins",
    categoryCode: "doctor",
    visual: "consultation",
    image: "/images/teleconsultation.webp",
    photographer: "Tima Miroshnichenko",
  },
  {
    id: "pharmacies",
    eyebrow: "PHARMACIES",
    title: "Les pharmacies de proximité.",
    description: "La rubrique pharmacie présentera les établissements qui auront rejoint le réseau et dont les informations pourront être publiées.",
    actionLabel: "Voir les pharmacies",
    categoryCode: "pharmacy",
    visual: "pharmacy",
    image: "/images/pharmacy.webp",
    photographer: "Abdul Batin",
  },
  {
    id: "laboratories",
    eyebrow: "ANALYSES MÉDICALES",
    title: "Les laboratoires, en toute clarté.",
    description: "Retrouvez prochainement les informations publiques des laboratoires inscrits et disponibles sur la plateforme.",
    actionLabel: "Voir les laboratoires",
    categoryCode: "laboratory",
    visual: "laboratory",
    image: "/images/laboratory.webp",
    photographer: "Pavel Danilyuk",
  },
  {
    id: "dentists",
    eyebrow: "SOINS DENTAIRES",
    title: "Les cabinets dentaires près de vous.",
    description: "La catégorie dentaire mettra en avant les cabinets qui auront choisi de rejoindre FANAFODIKO.",
    actionLabel: "Voir les dentistes",
    categoryCode: "dentist",
    visual: "dentist",
    image: "/images/dentistry.webp",
    photographer: "Arda Kaykısız",
  },
  {
    id: "specialists",
    eyebrow: "MÉDECINS ET SPÉCIALISTES",
    title: "Trouvez bientôt le bon interlocuteur.",
    description: "La recherche de médecins et de spécialistes sera disponible lorsque l’annuaire public sera ouvert.",
    actionLabel: "Voir les médecins",
    categoryCode: "doctor",
    visual: "specialists",
    image: "/images/doctor-specialist.webp",
    photographer: "Vitaly Gariev",
  },
];

export const professionalCategories = [
  {
    code: "pharmacy",
    title: "Pharmacies",
    icon: "pharmacy",
    description: "Informations de proximité sur les pharmacies et leurs services.",
    detail: "Cette rubrique accueillera les informations publiques des pharmacies inscrites et rendues visibles sur FANAFODIKO.",
  },
  {
    code: "doctor",
    title: "Médecins",
    icon: "doctor",
    description: "Médecins généralistes et spécialistes.",
    detail: "Cette rubrique présentera les profils de médecins dont l’inscription aura été validée et publiée.",
  },
  {
    code: "dentist",
    title: "Dentistes",
    icon: "dentist",
    description: "Cabinets dentaires et informations sur les soins dentaires.",
    detail: "Les informations des dentistes inscrits seront affichées quand un annuaire public sera disponible.",
  },
  {
    code: "laboratory",
    title: "Laboratoires médicaux",
    icon: "laboratory",
    description: "Laboratoires d’analyses médicales et services déclarés.",
    detail: "Cette catégorie réunira les informations publiables des laboratoires présents sur la plateforme. Certains laboratoires pourront proposer le prélèvement biologique à domicile, selon leur offre, la zone desservie et le type d’examen.",
  },
  {
    code: "delivery_courier",
    title: "Livreurs indépendants",
    icon: "courier",
    description: "Livreurs indépendants et zones de service déclarées.",
    detail: "Les livreurs indépendants pourront présenter leur activité après inscription et ouverture de l’annuaire.",
  },
  {
    code: "delivery_company",
    title: "Entreprises de livraison",
    icon: "company",
    description: "Entreprises de livraison et informations sur leurs services.",
    detail: "Cette rubrique présentera les entreprises inscrites lorsque leurs informations pourront être consultées publiquement.",
  },
];

export function nextSlideIndex(index, total) {
  return total > 0 ? (index + 1) % total : 0;
}

export function previousSlideIndex(index, total) {
  return total > 0 ? (index - 1 + total) % total : 0;
}

export function slideIndexForKey(key, index, total) {
  if (total <= 0) return 0;
  if (key === "ArrowRight") return nextSlideIndex(index, total);
  if (key === "ArrowLeft") return previousSlideIndex(index, total);
  if (key === "Home") return 0;
  if (key === "End") return total - 1;
  return null;
}
