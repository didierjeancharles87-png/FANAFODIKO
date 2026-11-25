import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const admin = readFileSync(new URL("../components/AdminOperations.tsx", import.meta.url), "utf8");
const marketplaceAdmin = readFileSync(new URL("../components/MarketplaceAdmin.tsx", import.meta.url), "utf8");
const partner = readFileSync(new URL("../components/PartnerSpace.tsx", import.meta.url), "utf8");
const client = readFileSync(new URL("../components/ClientSpace.tsx", import.meta.url), "utf8");
const phase7 = readFileSync(new URL("./phase7.mjs", import.meta.url), "utf8");

test("l'administration affiche les réservations avec le libellé central", () => {
  assert.ok(admin.includes('import { orderStatusLabel, statusLabel } from "@/lib/status-labels.mjs";'));
  assert.ok(admin.includes("{orderStatusLabel(order.status)}"));
  assert.ok(!admin.includes("{order.status}"));
});

test("l'administration traduit tous les statuts techniques restants", () => {
  assert.ok(admin.includes('statusLabel("confirmation", item.status)'));
  assert.ok(admin.includes('statusLabel("professionalVerification", profile.verification_status)'));
  assert.ok(admin.includes('statusLabel("account", profile.account_status)'));
  assert.ok(admin.includes('statusLabel("documentReview", document.review_status)'));
  assert.ok(admin.includes('statusLabel("sellerVerification", seller.verification_status)'));
  assert.ok(admin.includes('statusLabel("professionalVerification", seller.professional_status)'));
  assert.ok(admin.includes('statusLabel("professionalVerification", account.professional_status)'));
  assert.ok(admin.includes('statusLabel("authorization", product.authorization_status)'));
});

test("la gestion du catalogue traduit ses statuts avec le même registre", () => {
  assert.ok(marketplaceAdmin.includes('import { statusLabel } from "@/lib/status-labels.mjs";'));
  assert.ok(marketplaceAdmin.includes('statusLabel("professionalVerification", item.verification_status)'));
  assert.ok(marketplaceAdmin.includes('statusLabel("professionalVerification", seller.professional_status)'));
  assert.ok(marketplaceAdmin.includes('statusLabel("authorization", product.authorization_status)'));
  assert.ok(marketplaceAdmin.includes('statusLabel("authorization", "verified")'));
  assert.ok(marketplaceAdmin.includes('statusLabel("authorization", "rejected")'));
});

test("l'historique fournisseur corrige le statut initial et garde les transitions centralisées", () => {
  assert.ok(partner.includes('import { orderHistoryFromLabel, orderStatusLabel } from "@/lib/status-labels.mjs";'));
  assert.ok(partner.includes("{orderHistoryFromLabel(event.from_status)} → {orderStatusLabel(event.to_status)}"));
  assert.ok(!partner.includes("orderStatusLabel(event.from_status)"));
});

test("l'espace acheteur et le module de suivi partagent la même source", () => {
  assert.ok(client.includes("orderStatusLabel(order.status)"));
  assert.ok(client.includes("orderTimeline(order)"));
  assert.ok(phase7.includes('import { ORDER_STATUS_LABELS, orderStatusLabel } from "./status-labels.mjs";'));
  assert.ok(phase7.includes("export { orderStatusLabel };"));
  assert.ok(phase7.includes("label: ORDER_STATUS_LABELS[status]"));
});
