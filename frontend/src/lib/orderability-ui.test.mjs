import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const clientSpace = readFileSync(new URL("../components/ClientSpace.tsx", import.meta.url), "utf8");
const marketplace = readFileSync(new URL("../components/MarketplacePublic.tsx", import.meta.url), "utf8");
const types = readFileSync(new URL("./marketplace.d.mts", import.meta.url), "utf8");

test("the reservation form is only rendered for an orderable product", () => {
  assert.match(clientSpace, /export function AddToCartButton\([^)]*isOrderable/);
  assert.match(clientSpace, /if \(!isOrderable\) return;/);
  assert.match(clientSpace, /isOrderable \? <>/);
  assert.match(clientSpace, /Réservation indisponible/);
  assert.match(clientSpace, /unavailableReason\?\.trim\(\)/);
});

test("the public detail passes the server decision to the reservation button", () => {
  assert.match(marketplace, /isOrderable=\{product\.is_orderable\}/);
  assert.match(marketplace, /unavailableReason=\{product\.orderability_reason\}/);
});

test("the public product type exposes the server orderability fields", () => {
  assert.match(types, /is_orderable: boolean/);
  assert.match(types, /orderability_reason: string \| null/);
});
