import test from "node:test";
import assert from "node:assert/strict";
import { countryListFromApi, countryLoadErrorMessage } from "./country-list.mjs";

test("accepts the existing public country endpoint response shape", () => {
  const countries = [{ id: 1, code_alpha2: "MG", code_alpha3: "MDG", name_fr: "Madagascar", name_en: "Madagascar" }];
  assert.deepEqual(countryListFromApi(countries), countries);
});

test("treats an empty country list as a valid response", () => {
  assert.deepEqual(countryListFromApi([]), []);
});

test("rejects malformed country responses", () => {
  assert.throws(() => countryListFromApi({ results: [] }), /réponse de l’API des pays est invalide/i);
  assert.throws(() => countryListFromApi([{ id: "1", name_fr: "Madagascar", code_alpha2: "MG" }]), /réponse de l’API des pays est invalide/i);
});

test("explains API, access, and network failures separately", () => {
  assert.match(countryLoadErrorMessage({ status: 503 }), /503/);
  assert.match(countryLoadErrorMessage({ status: 403 }), /refusé/);
  assert.match(countryLoadErrorMessage(new TypeError("Failed to fetch")), /API est démarrée/);
});
