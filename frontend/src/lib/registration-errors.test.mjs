import { test } from "node:test";
import assert from "node:assert/strict";
import { registrationFieldErrors } from "./registration-errors.js";

test("maps Django registration validation errors to their form fields", () => {
  assert.deepEqual(registrationFieldErrors({
    category: ["Sélectionnez un choix valide."],
    password: ["Ce mot de passe est trop courant."],
    contact_phone: ["Saisissez un numéro valide."],
    non_field_errors: ["ignored"],
  }), {
    category: "Catégorie professionnelle : Sélectionnez un choix valide.",
    password: "Mot de passe : Ce mot de passe est trop courant.",
    contact_phone: "Téléphone de contact : Saisissez un numéro valide.",
  });
});

test("ignores missing and non-object error details", () => {
  assert.deepEqual(registrationFieldErrors(null), {});
  assert.deepEqual(registrationFieldErrors("invalid"), {});
});
