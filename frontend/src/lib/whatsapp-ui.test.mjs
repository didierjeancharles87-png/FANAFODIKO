import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const floating = readFileSync(new URL("../components/WhatsAppFloating.tsx", import.meta.url), "utf8");
const administration = readFileSync(new URL("../components/AdministrationContent.tsx", import.meta.url), "utf8");

test("the public WhatsApp button has no environment fallback", () => {
  assert.doesNotMatch(floating, /NEXT_PUBLIC_WHATSAPP_NUMBER/);
  assert.match(floating, /public\/configuration/);
  assert.match(floating, /createWhatsAppLink/);
});

test("the administration form has no environment fallback and explains a missing number", () => {
  assert.doesNotMatch(administration, /NEXT_PUBLIC_WHATSAPP_NUMBER/);
  assert.match(administration, /admin\/configuration/);
  assert.match(administration, /WhatsApp n’est pas configuré/);
  assert.match(administration, /Enregistrer le numéro/);
  assert.match(administration, /Aucun message n’est envoyé automatiquement/);
});
