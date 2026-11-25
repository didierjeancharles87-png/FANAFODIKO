// Référence unique des libellés affichés pour les statuts.
// Les clés restent exactement les valeurs techniques enregistrées par le backend :
// aucune valeur stockée ni transition métier n'est modifiée ici.

export const ORDER_CREATION_LABEL = "Réservation créée";
export const EMPTY_STATUS_LABEL = "—";
export const UNKNOWN_STATUS_LABEL = "Statut inconnu";

export const ORDER_STATUS_LABELS = Object.freeze({
  awaiting_seller: "En attente du vendeur",
  accepted: "Acceptée",
  rejected: "Refusée",
  preparing: "En préparation",
  ready: "Prête pour retrait",
  completed: "Finalisée",
  cancelled: "Annulée",
});

export const STATUS_LABELS = Object.freeze({
  order: ORDER_STATUS_LABELS,
  confirmation: Object.freeze({
    pending: "En attente",
    approved: "Approuvée",
    rejected: "Refusée",
  }),
  professionalVerification: Object.freeze({
    draft: "Brouillon",
    pending: "En attente",
    approved: "Approuvé",
    rejected: "Refusé",
  }),
  sellerVerification: Object.freeze({
    pending: "À vérifier",
    verified: "Vérifié",
    rejected: "Refusé",
  }),
  account: Object.freeze({
    active: "Actif",
    suspended: "Suspendu",
    closed: "Clôturé",
  }),
  documentReview: Object.freeze({
    pending: "À examiner",
    accepted: "Accepté",
    rejected: "Refusé",
  }),
  authorization: Object.freeze({
    pending: "À vérifier",
    verified: "AMM vérifiée",
    rejected: "AMM refusée",
  }),
});

function isBlank(value) {
  return value === null || value === undefined || String(value).trim() === "";
}

export function statusLabel(domain, value) {
  const labels = STATUS_LABELS[domain];
  if (!labels) return UNKNOWN_STATUS_LABEL;
  if (isBlank(value)) return EMPTY_STATUS_LABEL;
  return labels[value] ?? UNKNOWN_STATUS_LABEL;
}

export function orderStatusLabel(value) {
  if (isBlank(value)) return UNKNOWN_STATUS_LABEL;
  return ORDER_STATUS_LABELS[value] ?? UNKNOWN_STATUS_LABEL;
}

export function orderHistoryFromLabel(value) {
  if (isBlank(value)) return ORDER_CREATION_LABEL;
  return orderStatusLabel(value);
}
