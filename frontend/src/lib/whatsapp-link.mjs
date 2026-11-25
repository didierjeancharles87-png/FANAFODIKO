/** @param {unknown} value @returns {string | null} */
export function normalizeWhatsAppNumber(value) {
  if (typeof value !== "string") return null;
  const normalized = value.trim().replace(/[\s().-]/g, "");
  if (!/^\+?[1-9]\d{7,14}$/.test(normalized)) return null;
  return normalized.replace(/\D/g, "");
}

/** @param {unknown} value @param {string} message @returns {string | null} */
export function createWhatsAppLink(value, message) {
  const digits = normalizeWhatsAppNumber(value);
  return digits ? `https://wa.me/${digits}?text=${encodeURIComponent(message)}` : null;
}
