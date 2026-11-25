/** @typedef {{ id: number, name_fr: string, code_alpha2: string }} CountryRecord */

/** @param {unknown} value @returns {CountryRecord[]} */
export function countryListFromApi(value) {
  if (!Array.isArray(value) || value.some((country) =>
    !country || typeof country !== "object" ||
    !Number.isInteger(country.id) || typeof country.name_fr !== "string" ||
    typeof country.code_alpha2 !== "string"
  )) {
    throw new Error("La réponse de l’API des pays est invalide.");
  }
  return value;
}

/** @param {unknown} error @returns {string} */
export function countryLoadErrorMessage(error) {
  if (error instanceof Error && error.message === "La réponse de l’API des pays est invalide.") {
    return error.message;
  }
  if (error && typeof error === "object" && "status" in error && typeof error.status === "number") {
    if (error.status === 401 || error.status === 403) {
      return "L’accès à la liste des pays a été refusé par l’API.";
    }
    return `L’API des pays a répondu avec une erreur (${error.status}). Réessayez plus tard.`;
  }
  return "Impossible de joindre l’API des pays. Vérifiez que l’API est démarrée et accessible depuis ce site.";
}
