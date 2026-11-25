import test from "node:test";
import assert from "node:assert/strict";
import { availabilityLabel, catalogDetailHref, formatMGA, formatMarketplaceDate, marketplaceTypes } from "./marketplace.mjs";

test("catalog categories link only to real catalogue routes", () => {
  assert.deepEqual(marketplaceTypes.map(({ href }) => href), ["/medicaments", "/materiel-medical"]);
});

test("catalog texts describe reservations without online payment", () => {
  assert.match(marketplaceTypes[0].description, /réservation sans paiement en ligne/);
  assert.doesNotMatch(marketplaceTypes[0].description, /Aucune commande/);
  assert.match(marketplaceTypes[0].description, /pharmacie partenaire/);
});

test("prices are consistently displayed in Ariary", () => {
  assert.match(formatMGA("12500.00"), /Ar$/);
  assert.equal(formatMGA("invalid"), "Prix non disponible");
});

test("catalog labels include current dates, availability and product details routes", () => {
  assert.equal(availabilityLabel("available"), "Disponible selon la dernière mise à jour");
  assert.equal(catalogDetailHref({ product_type: "medicine", slug: "test" }), "/medicaments/test");
  assert.equal(catalogDetailHref({ product_type: "equipment", slug: "test" }), "/materiel-medical/test");
  assert.match(formatMarketplaceDate("2026-11-25T09:00:00Z"), /2026/);
});
