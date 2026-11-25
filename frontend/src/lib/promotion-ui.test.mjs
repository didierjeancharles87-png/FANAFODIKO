import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const partner = readFileSync(new URL("../components/PartnerSpace.tsx", import.meta.url), "utf8");
const client = readFileSync(new URL("../components/ClientSpace.tsx", import.meta.url), "utf8");
const packageJson = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8"));

test("partner promotions use the dedicated API without sending prices", () => {
  assert.match(partner, /apiFetch<PartnerPromotion\[\]>\("\/v1\/promotions\/partner\/"\)/);
  assert.match(partner, /\/v1\/promotions\/partner\/\$\{promotion.id\}\/activate\//);
  assert.match(partner, /\/v1\/promotions\/partner\/\$\{promotion.id\}\/deactivate\//);
  assert.match(partner, /\/v1\/promotions\/partner\/\$\{promotion.id\}\/request-removal\//);
  assert.match(partner, /\/v1\/promotions\/partner\/\$\{id\}\/results\//);
  assert.match(partner, /starts_at: fromDateTimeLocal\(/);
  assert.match(partner, /ends_at: fromDateTimeLocal\(/);
  assert.doesNotMatch(partner, /name="(original|promotional)_price_mga"/);
});

test("buyer cart and order detail rely on server coupon and timeline data", () => {
  assert.match(client, /\/v1\/cart\/coupon\//);
  assert.match(client, /orderTimeline\(order\)/);
  assert.match(client, /\/v1\/accounts\/patient\/addresses\//);
  assert.match(client, /delivery_recipient \? `Destinataire/);
  assert.match(client, /Coordonnées figées au moment de la réservation/);
});

test("promotion, address and partner pages are registered", () => {
  const routes = [
    "../app/promotions/page.tsx",
    "../app/patient/adresses/page.tsx",
    "../app/partenaire/promotions/page.tsx",
  ];
  for (const route of routes) assert.equal(existsSync(new URL(route, import.meta.url)), true, route);
});

test("the test runner includes promotion helper and UI checks", () => {
  assert.match(packageJson.scripts.test, /promotions\.test\.mjs/);
  assert.match(packageJson.scripts.test, /promotion-ui\.test\.mjs/);
});
