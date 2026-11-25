import test from "node:test";
import assert from "node:assert/strict";
import {
  NO_ONLINE_PAYMENT_NOTICE,
  PRESCRIPTION_NOTICE,
  PICKUP_NOTICE,
  RESERVATION_NOTICE,
  canSubmitForReview,
  moderationStatusLabel,
  notificationTypeLabel,
  orderConfirmationHref,
  orderStatusLabel,
  orderTimeline,
  orderTrackingHref,
} from "./phase7.mjs";

test("les messages obligatoires excluent tout paiement en ligne", () => {
  assert.match(NO_ONLINE_PAYMENT_NOTICE, /Aucun paiement en ligne/);
  assert.match(NO_ONLINE_PAYMENT_NOTICE, /partenaire/);
  assert.match(PICKUP_NOTICE, /retrait/);
  assert.match(PRESCRIPTION_NOTICE, /ordonnance/);
  assert.match(PRESCRIPTION_NOTICE, /ne stocke ni image/);
  assert.equal(RESERVATION_NOTICE.includes(NO_ONLINE_PAYMENT_NOTICE), true);
  assert.equal(RESERVATION_NOTICE.includes(PICKUP_NOTICE), true);
});

test("les libellés de suivi couvrent le cycle de vie réel", () => {
  assert.equal(orderStatusLabel("awaiting_seller"), "En attente du vendeur");
  assert.equal(orderStatusLabel("ready"), "Prête pour retrait");
  assert.equal(moderationStatusLabel("pending"), "En attente de modération");
  assert.equal(notificationTypeLabel("stock_depleted"), "Stock épuisé");
  assert.equal(orderStatusLabel("inconnu"), "Statut inconnu");
});

test("la soumission est refusée uniquement pour un produit archivé", () => {
  assert.equal(canSubmitForReview({ status: "draft" }), true);
  assert.equal(canSubmitForReview({ status: "rejected" }), true);
  assert.equal(canSubmitForReview({ status: "archived" }), false);
  assert.equal(canSubmitForReview(null), false);
});

test("les liens de suivi utilisent la référence de réservation", () => {
  const order = { id: 12, reference: "FMD-20261125-ABC123" };
  assert.equal(orderTrackingHref(order), "/commandes/FMD-20261125-ABC123");
  assert.equal(orderConfirmationHref(order), "/commandes/confirmation/FMD-20261125-ABC123");
  assert.equal(orderTrackingHref({ id: 7 }), "/commandes/7");
  assert.equal(orderTrackingHref(null), "/commandes");
});

test("la timeline visuelle reste fondée sur les événements serveur", () => {
  const steps = orderTimeline({
    status: "accepted",
    events: [
      { to_status: "awaiting_seller", note: "Réservation créée.", created_at: "2026-11-25T08:00:00Z" },
      { to_status: "accepted", note: "Acceptée par le vendeur.", created_at: "2026-11-25T09:00:00Z" },
    ],
  });
  assert.deepEqual(steps.map(({ status, done, current }) => [status, done, current]), [
    ["awaiting_seller", true, false],
    ["accepted", true, true],
    ["preparing", false, false],
    ["ready", false, false],
    ["completed", false, false],
  ]);
  assert.equal(steps[1].note, "Acceptée par le vendeur.");
  assert.deepEqual(orderTimeline(null), []);
});
