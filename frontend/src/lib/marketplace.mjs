export const marketplaceTypes = [
  { id: "medicine", title: "Médicaments", href: "/medicaments", description: "Consultez les fiches publiées par des pharmacies vérifiées. Une réservation sans paiement en ligne peut être créée ; la délivrance se fait auprès de la pharmacie partenaire." },
  { id: "equipment", title: "Matériel médical", href: "/materiel-medical", description: "Découvrez le matériel médical publié par des fournisseurs vérifiés, avec ses caractéristiques et sa disponibilité déclarée." },
];

export function formatMGA(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "Prix non disponible";
  return `${new Intl.NumberFormat("fr-MG", { maximumFractionDigits: 0 }).format(amount)} Ar`;
}

export function formatMarketplaceDate(value) {
  if (!value) return "Date non disponible";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date non disponible";
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}

export function availabilityLabel(value) {
  return ({ available: "Disponible selon la dernière mise à jour", limited: "Disponibilité limitée", unavailable: "Indisponible" })[value] ?? "Disponibilité non renseignée";
}

export function catalogDetailHref(product) {
  return product.product_type === "medicine" ? `/medicaments/${product.slug}` : `/materiel-medical/${product.slug}`;
}
