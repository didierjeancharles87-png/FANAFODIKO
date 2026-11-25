import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const patientLogin = readFileSync(new URL("../app/patient/connexion/page.tsx", import.meta.url), "utf8");
const professionalLogin = readFileSync(new URL("../app/professionnel/connexion/page.tsx", import.meta.url), "utf8");

test("patient login captures form data before awaiting CSRF", () => {
  const capture = "const formData = new FormData(event.currentTarget);";
  const csrf = 'await apiFetch("/v1/auth/csrf/");';
  const formFields = patientLogin.match(/event\.currentTarget/g) ?? [];

  assert.equal(formFields.length, 1, "event.currentTarget must only be read before the first await");
  assert.ok(patientLogin.indexOf(capture) >= 0, "FormData must be captured synchronously");
  assert.ok(patientLogin.indexOf(csrf) > patientLogin.indexOf(capture), "CSRF request must come after the capture");
});

test("patient login sends the captured credentials with the POST login request", () => {
  assert.match(patientLogin, /await apiFetch<AuthSession>\("\/v1\/auth\/login\/"/);
  assert.match(patientLogin, /method: "POST"/);
  assert.match(patientLogin, /body: JSON\.stringify\(Object\.fromEntries\(formData\)\)/);
  assert.match(patientLogin, /headers: \{ "Content-Type": "application\/json" \}/);
});

test("patient login keeps the patient session and only logs out other roles", () => {
  const guardIndex = patientLogin.indexOf('if (!session.roles.includes("patient"))');
  const logoutIndex = patientLogin.indexOf('await apiFetch("/v1/auth/logout/", { method: "POST" })');
  const errorIndex = patientLogin.indexOf("Ce compte n’a pas le rôle patient");
  const redirectIndex = patientLogin.indexOf('router.replace("/patient/profil")');

  assert.ok(guardIndex >= 0, "the patient role guard must remain");
  assert.ok(logoutIndex > guardIndex && logoutIndex < errorIndex, "only a non-patient session is logged out");
  assert.ok(redirectIndex > guardIndex, "a patient session is kept and redirected to the patient profile");
  assert.match(patientLogin, /caught instanceof ApiError \? caught\.message : "La connexion a échoué\."/);
});

test("professional login keeps the same safe FormData ordering", () => {
  const capture = "const data = new FormData(event.currentTarget);";
  const csrf = 'await apiFetch("/v1/auth/csrf/");';

  assert.ok(professionalLogin.indexOf(capture) >= 0, "professional form data must also be captured synchronously");
  assert.ok(professionalLogin.indexOf(csrf) > professionalLogin.indexOf(capture));
});
