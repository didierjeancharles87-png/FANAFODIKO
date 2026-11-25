import { ORDER_STATUS_LABELS, orderStatusLabel } from "./status-labels.mjs";

export { orderStatusLabel };

export const NO_ONLINE_PAYMENT_NOTICE =
  "Aucun paiement en ligne n’est effectué sur FANAFODIKO. Le règlement se fait directement auprès du partenaire.";

export const PICKUP_NOTICE =
  "Le retrait s’effectue auprès du vendeur partenaire après acceptation de la réservation.";

export const PRESCRIPTION_NOTICE =
  "Pour un médicament nécessitant une ordonnance, le pharmacien doit confirmer explicitement que l’ordonnance a été vérifiée. FANAFODIKO ne stocke ni image, ni numéro, ni contenu d’ordonnance et ne réalise aucune validation médicale.";

export const RESERVATION_NOTICE = `${NO_ONLINE_PAYMENT_NOTICE} ${PICKUP_NOTICE}`;

const moderationLabels = {
  not_required: "Non requise",
  pending: "En attente de modération",
  approved: "Approuvée",
  rejected: "Refusée",
};

const notificationLabels = {
  order_created: "Réservation créée",
  order_accepted: "Commande acceptée",
  order_rejected: "Commande refusée",
  order_preparing: "Commande en préparation",
  order_ready: "Réservation prête",
  order_completed: "Commande finalisée",
  order_cancelled: "Commande annulée",
  moderation_approved: "Produit approuvé",
  moderation_rejected: "Produit refusé",
  stock_depleted: "Stock épuisé",
};

export function moderationStatusLabel(value) {
  return moderationLabels[value] ?? "Modération inconnue";
}

export function notificationTypeLabel(value) {
  return notificationLabels[value] ?? "Notification";
}

export function canSubmitForReview(product) {
  return Boolean(product && product.status !== "archived");
}

export function orderTrackingHref(order) {
  const reference = order && typeof order.reference === "string" ? order.reference : "";
  return reference ? `/commandes/${encodeURIComponent(reference)}` : order?.id ? `/commandes/${order.id}` : "/commandes";
}

export function orderConfirmationHref(order) {
  const reference = order && typeof order.reference === "string" ? order.reference : "";
  return reference
    ? `/commandes/confirmation/${encodeURIComponent(reference)}`
    : order?.id
      ? `/commandes/confirmation/${order.id}`
      : "/commandes";
}

export const orderFlow = ["awaiting_seller", "accepted", "preparing", "ready", "completed"];

export function orderTimeline(order) {
  if (!order) return [];
  const reached = new Map();
  for (const event of order.events ?? []) {
    if (!event.to_status) continue;
    const previous = reached.get(event.to_status);
    if (!previous || String(event.created_at ?? "") > String(previous.created_at ?? "")) reached.set(event.to_status, event);
  }
  const currentIndex = orderFlow.indexOf(order.status);
  return orderFlow.map((status, index) => {
    const event = reached.get(status);
    return {
      status,
      label: ORDER_STATUS_LABELS[status],
      at: event?.created_at ?? null,
      note: event?.note ?? "",
      done: Boolean(event) || (currentIndex >= 0 && index < currentIndex),
      current: order.status === status,
    };
  });
}
