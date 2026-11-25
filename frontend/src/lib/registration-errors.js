const FIELD_LABELS = {
  category: "Catégorie professionnelle",
  legal_name: "Nom ou raison sociale",
  email: "Adresse e-mail",
  contact_phone: "Téléphone de contact",
  password: "Mot de passe",
};

/** Convert Django REST Framework field errors into concise French field messages. */
export function registrationFieldErrors(details) {
  if (!details || typeof details !== "object" || Array.isArray(details)) return {};

  const result = {};
  for (const [field, value] of Object.entries(details)) {
    if (!(field in FIELD_LABELS)) continue;
    const messages = Array.isArray(value) ? value : [value];
    const message = messages.find((item) => typeof item === "string");
    if (message) result[field] = `${FIELD_LABELS[field]} : ${message}`;
  }
  return result;
}
