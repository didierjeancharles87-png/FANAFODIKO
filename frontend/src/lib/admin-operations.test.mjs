import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../components/AdminOperations.tsx", import.meta.url), "utf8");

test("administration lists accept both array and paginated API responses", () => {
  assert.match(source, /apiFetch<Order\[\] \| Page<Order>>\("\/v1\/admin\/orders\/"\)/);
  assert.match(source, /apiFetch<Notification\[\] \| Page<Notification>>\("\/v1\/notifications\/"\)/);
  assert.match(source, /Array\.isArray\(orderData\) \? orderData : orderData\.results \?\? \[\]/);
  assert.match(source, /Array\.isArray\(notificationData\) \? notificationData : notificationData\.results \?\? \[\]/);
});

test("administration options come from the admin marketplace endpoint", () => {
  assert.match(source, /apiFetch<Options>\("\/v1\/marketplace\/admin\/options\/"\)/);
  assert.match(source, /optionData\.accounts \?\? \[\]/);
});

test("central administration validates promotions without publishing them directly", () => {
  assert.match(source, /apiFetch<Promotion\[\]>\("\/v1\/promotions\/admin\/"\)/);
  assert.match(source, /setPromotions\(promotionData\)/);
  assert.match(source, /\/v1\/promotions\/admin\/\$\{promotion.id\}\/\$\{decision\}\//);
  assert.match(source, /decision === "reject" \? \{ reason \} : \{\}/);
  assert.match(source, /\/v1\/promotions\/admin\/\$\{promotion.id\}\/archive\//);
  assert.doesNotMatch(source, /\/v1\/promotions\/partner\/\$\{promotion.id\}\/activate\//);
});
