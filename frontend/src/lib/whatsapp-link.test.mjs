import test from "node:test";
import assert from "node:assert/strict";
import { createWhatsAppLink, normalizeWhatsAppNumber } from "./whatsapp-link.mjs";

test("normalizes the configured official number for wa.me", () => {
  assert.equal(normalizeWhatsAppNumber("261381627248"), "261381627248");
  assert.equal(normalizeWhatsAppNumber("+261 38 16 27 248"), "261381627248");
});

test("does not create a WhatsApp link for missing or invalid numbers", () => {
  assert.equal(createWhatsAppLink("", "Bonjour"), null);
  assert.equal(createWhatsAppLink("not-a-number", "Bonjour"), null);
  assert.equal(createWhatsAppLink("123", "Bonjour"), null);
});

test("encodes the message in the generated WhatsApp link", () => {
  assert.equal(createWhatsAppLink("261381627248", "Bonjour, FANAFODIKO"), "https://wa.me/261381627248?text=Bonjour%2C%20FANAFODIKO");
});
