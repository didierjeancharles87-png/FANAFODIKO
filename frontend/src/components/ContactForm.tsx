"use client";

import { useState, type FormEvent } from "react";

export function ContactForm() {
  const [notice, setNotice] = useState("");
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("Aucun message n’a été envoyé : le formulaire est encore en préparation.");
  }
  return <form className="info-card grid gap-4" onSubmit={handleSubmit}>
    <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">Formulaire non opérationnel : les données saisies restent dans cette page et ne sont pas transmises.</p>
    <label className="form-label">Nom<input className="form-input" name="name" autoComplete="name" maxLength={120} required /></label>
    <label className="form-label">Adresse e-mail<input className="form-input" name="email" type="email" autoComplete="email" maxLength={254} required /></label>
    <label className="form-label">Sujet<input className="form-input" name="subject" maxLength={160} required /></label>
    <label className="form-label">Message<textarea className="form-input min-h-36" name="message" maxLength={3000} required /></label>
    <button type="submit" className="button-primary w-fit">Vérifier le formulaire</button>
    <p aria-live="polite" role="status" className="text-sm font-medium text-amber-800">{notice}</p>
    <p className="text-xs leading-5 text-slate-500">N’indiquez pas de données de santé ou d’informations confidentielles. Aucun message n’est envoyé par ce formulaire.</p>
  </form>;
}
