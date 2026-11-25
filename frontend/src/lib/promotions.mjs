export const PROMOTION_NOTICE =
  "Une promotion n’est visible publiquement qu’après validation par l’administration FANAFODIKO et activation par le vendeur partenaire.";

export const COUPON_NOTICE =
  "Le coupon s’applique uniquement au produit concerné, dans sa période de validité et dans la limite de quantité déclarée. Les prix et remises sont calculés par le serveur.";

export function promotionBadge(promotion) {
  return promotion && promotion.status === "active" ? "PROMO" : "";
}

export function promotionDiscount(promotion) {
  return promotion?.discount_label ?? "";
}

export function promotionPrice(product) {
  if (!product) return "";
  return product.effective_price_mga || product.price_mga || "";
}

export function promotionConditions(promotion) {
  if (!promotion) return [];
  const conditions = [];
  if (promotion.code) conditions.push(`Code coupon : ${promotion.code}`);
  if (promotion.ends_at) {
    const endDate = new Date(promotion.ends_at);
    if (!Number.isNaN(endDate.getTime())) {
      conditions.push(`Valable jusqu’au ${new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(endDate)}`);
    }
  }
  if (promotion.max_redemptions !== null && promotion.max_redemptions !== undefined) {
    conditions.push(`Quantité limitée à ${promotion.max_redemptions} reservation(s)`);
  }
  if (promotion.remaining_quantity !== null && promotion.remaining_quantity !== undefined) {
    conditions.push(`${promotion.remaining_quantity} restante(s)`);
  }
  return conditions;
}

export function couponSummary(cart) {
  const applied = Boolean(cart?.coupon_code);
  return {
    applied,
    code: cart?.coupon_code ?? "",
    error: cart?.coupon_error ?? "",
    discount: cart?.discount_mga ?? "",
    message: applied ? `Coupon ${cart.coupon_code} appliqué par le serveur.` : "",
  };
}

export function promotionStatusLabel(status) {
  return ({
    pending: "En attente de validation administrative",
    approved: "Validée — activation par le vendeur requise",
    rejected: "Refusée",
    active: "Active et visible publiquement",
    paused: "Désactivée par le vendeur",
    removal_requested: "Archivage demandé",
    archived: "Archivée",
  })[status] ?? "Statut inconnu";
}

export function canRequestPromotionRemoval(promotion) {
  return Boolean(promotion && !["removal_requested", "archived"].includes(promotion.status));
}

export function canEditPromotion(promotion) {
  return Boolean(promotion && ["pending", "rejected"].includes(promotion.status));
}

export function toDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fromDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}
