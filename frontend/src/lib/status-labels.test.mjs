import test from "node:test";
import assert from "node:assert/strict";
import {
  EMPTY_STATUS_LABEL,
  ORDER_CREATION_LABEL,
  ORDER_STATUS_LABELS,
  STATUS_LABELS,
  UNKNOWN_STATUS_LABEL,
  orderHistoryFromLabel,
  orderStatusLabel,
  statusLabel,
} from "./status-labels.mjs";
import { orderStatusLabel as buyerOrderStatusLabel, orderTimeline } from "./phase7.mjs";

const expected = {
  order: {
    awaiting_seller: "En attente du vendeur",
    accepted: "Acceptée",
    rejected: "Refusée",
    preparing: "En préparation",
    ready: "Prête pour retrait",
    completed: "Finalisée",
    cancelled: "Annulée",
  },
  confirmation: {
    pending: "En attente",
    approved: "Approuvée",
    rejected: "Refusée",
  },
  professionalVerification: {
    draft: "Brouillon",
    pending: "En attente",
    approved: "Approuvé",
    rejected: "Refusé",
  },
  sellerVerification: {
    pending: "À vérifier",
    verified: "Vérifié",
    rejected: "Refusé",
  },
  account: {
    active: "Actif",
    suspended: "Suspendu",
    closed: "Clôturé",
  },
  documentReview: {
    pending: "À examiner",
    accepted: "Accepté",
    rejected: "Refusé",
  },
  authorization: {
    pending: "À vérifier",
    verified: "AMM vérifiée",
    rejected: "AMM refusée",
  },
};

test("chaque statut de réservation possède un libellé français centralisé", () => {
  assert.deepEqual({ ...ORDER_STATUS_LABELS }, expected.order);
  for (const [status, label] of Object.entries(expected.order)) {
    assert.equal(orderStatusLabel(status), label, `orderStatusLabel(${status})`);
    assert.equal(statusLabel("order", status), label, `statusLabel(order, ${status})`);
  }
});

test("chaque statut affiché dans l'administration possède un libellé français centralisé", () => {
  for (const [domain, labels] of Object.entries(expected)) {
    if (domain === "order") continue;
    assert.deepEqual({ ...STATUS_LABELS[domain] }, labels, `registre ${domain}`);
    for (const [status, label] of Object.entries(labels)) {
      assert.equal(statusLabel(domain, status), label, `statusLabel(${domain}, ${status})`);
    }
  }
});

test("aucun libellé ne laisse paraître la valeur technique", () => {
  for (const [domain, labels] of Object.entries(STATUS_LABELS)) {
    for (const [status, label] of Object.entries(labels)) {
      assert.notEqual(label, status, `${domain}.${status}`);
      assert.ok(!label.includes("_"), `${domain}.${status} → ${label}`);
    }
  }
});

test("l'historique affiche la création pour l'événement initial", () => {
  assert.equal(orderHistoryFromLabel(""), ORDER_CREATION_LABEL);
  assert.equal(orderHistoryFromLabel(null), ORDER_CREATION_LABEL);
  assert.equal(orderHistoryFromLabel(undefined), ORDER_CREATION_LABEL);
  assert.equal(orderHistoryFromLabel("awaiting_seller"), "En attente du vendeur");
  assert.equal(orderHistoryFromLabel("completed"), "Finalisée");
  assert.equal(orderHistoryFromLabel("inconnu"), UNKNOWN_STATUS_LABEL);
});

test("les valeurs vides et inconnues ont un repli explicite", () => {
  assert.equal(orderStatusLabel(""), UNKNOWN_STATUS_LABEL);
  assert.equal(orderStatusLabel(null), UNKNOWN_STATUS_LABEL);
  assert.equal(orderStatusLabel("inconnu"), UNKNOWN_STATUS_LABEL);
  assert.equal(statusLabel("account", ""), EMPTY_STATUS_LABEL);
  assert.equal(statusLabel("account", null), EMPTY_STATUS_LABEL);
  assert.equal(statusLabel("account", "inconnu"), UNKNOWN_STATUS_LABEL);
  assert.equal(statusLabel("domaineInconnu", "active"), UNKNOWN_STATUS_LABEL);
});

test("l'espace acheteur consomme le même registre central", () => {
  assert.equal(buyerOrderStatusLabel("awaiting_seller"), "En attente du vendeur");
  assert.equal(buyerOrderStatusLabel("completed"), "Finalisée");
  const steps = orderTimeline({
    status: "completed",
    events: [{ to_status: "awaiting_seller", note: "Réservation créée.", created_at: "2026-11-25T08:00:00Z" }],
  });
  assert.equal(steps[0].label, "En attente du vendeur");
  assert.equal(steps[4].label, "Finalisée");
});
