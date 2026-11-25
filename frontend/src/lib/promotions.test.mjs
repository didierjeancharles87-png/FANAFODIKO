import test from "node:test";
import assert from "node:assert/strict";
import {
  PROMOTION_NOTICE,
  COUPON_NOTICE,
  canEditPromotion,
  couponSummary,
  fromDateTimeLocal,
  promotionBadge,
  promotionConditions,
  promotionDiscount,
  promotionPrice,
  promotionStatusLabel,
  toDateTimeLocal,
} from "./promotions.mjs";

test("promotion notices keep administrative validation and server pricing explicit", () => {
  assert.match(PROMOTION_NOTICE, /validation par l’administration/);
  assert.match(COUPON_NOTICE, /calculés par le serveur/);
});

test("promotion badges and prices use only backend-provided values", () => {
  const promotion = { status: "active", discount_label: "-10 %" };
  assert.equal(promotionBadge(promotion), "PROMO");
  assert.equal(promotionDiscount(promotion), "-10 %");
  assert.equal(promotionBadge({ status: "pending" }), "");
  assert.equal(promotionPrice({ price_mga: "10000.00", effective_price_mga: "9000.00" }), "9000.00");
  assert.equal(promotionPrice({ price_mga: "10000.00" }), "10000.00");
});

test("promotion conditions expose coupon scope and limits without inventing stock", () => {
  const conditions = promotionConditions({
    code: "FANAFODIKO10",
    ends_at: "2026-12-31T00:00:00Z",
    max_redemptions: 5,
    remaining_quantity: 3,
  });
  assert.deepEqual(conditions, [
    "Code coupon : FANAFODIKO10",
    "Valable jusqu’au 31/12/2026",
    "Quantité limitée à 5 reservation(s)",
    "3 restante(s)",
  ]);
  assert.deepEqual(promotionConditions(null), []);
  assert.deepEqual(promotionConditions({ ends_at: "date-invalide" }), []);
});

test("coupon summary reflects server state and never calculates a price", () => {
  assert.deepEqual(couponSummary({ coupon_code: "PROMO10", coupon_error: null, discount_mga: "1000.00" }), {
    applied: true,
    code: "PROMO10",
    error: "",
    discount: "1000.00",
    message: "Coupon PROMO10 appliqué par le serveur.",
  });
  assert.equal(couponSummary({ coupon_code: "", coupon_error: "expirée" }).error, "expirée");
});

test("promotion statuses expose the central validation workflow", () => {
  assert.match(promotionStatusLabel("pending"), /validation administrative/);
  assert.match(promotionStatusLabel("approved"), /activation par le vendeur/);
  assert.equal(promotionStatusLabel("active"), "Active et visible publiquement");
  assert.equal(canEditPromotion({ status: "pending" }), true);
  assert.equal(canEditPromotion({ status: "rejected" }), true);
  assert.equal(canEditPromotion({ status: "active" }), false);
});

test("datetime helpers preserve local input values for API payloads", () => {
  const local = toDateTimeLocal("2026-11-25T10:30:00Z");
  assert.match(local, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  assert.match(fromDateTimeLocal(local), /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:/);
  assert.equal(fromDateTimeLocal(""), "");
});
