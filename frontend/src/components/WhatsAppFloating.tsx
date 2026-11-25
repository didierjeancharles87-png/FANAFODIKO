"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { createWhatsAppLink } from "@/lib/whatsapp-link.mjs";

const greeting = "Bonjour, je souhaite obtenir des informations sur FANAFODIKO.";

export function WhatsAppFloating() {
  const [publicNumber, setPublicNumber] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void apiFetch<{ whatsapp_number: string; use_database_config: boolean }>("/v1/site-content/public/configuration/")
      .then(({ whatsapp_number, use_database_config }) => { if (active) setPublicNumber(use_database_config ? whatsapp_number : null); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);
  const href = createWhatsAppLink(publicNumber, greeting);
  if (!href) {
    if (process.env.NODE_ENV === "production") return null;
    return (
      <div className="whatsapp-unavailable" role="status" aria-label="WhatsApp non configuré">
        <WhatsAppIcon />
        <span>WhatsApp non configuré</span>
      </div>
    );
  }

  return (
    <a
      className="whatsapp-fab"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Besoin d'aide ? Contactez-nous sur WhatsApp"
      title="Besoin d'aide ? Contactez-nous sur WhatsApp"
    >
      <WhatsAppIcon />
      <span className="whatsapp-label">Besoin d&apos;aide ? Contactez-nous sur WhatsApp</span>
    </a>
  );
}

function WhatsAppIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 32 32" className="h-7 w-7" fill="currentColor">
      <path d="M16.02 3.2A12.68 12.68 0 0 0 5.14 22.4L3.5 28.4l6.16-1.62A12.68 12.68 0 1 0 16.02 3.2Zm0 22.98c-1.9 0-3.77-.51-5.4-1.48l-.39-.23-3.66.96.98-3.56-.25-.4a10.38 10.38 0 1 1 8.72 4.71Zm5.69-7.77c-.31-.16-1.84-.91-2.13-1.02-.29-.1-.5-.15-.71.16-.21.31-.81 1.02-.99 1.23-.18.21-.36.24-.67.08-.31-.15-1.3-.48-2.48-1.53-.92-.82-1.54-1.84-1.72-2.15-.18-.31-.02-.48.13-.63.14-.14.31-.36.46-.54.16-.18.21-.31.31-.52.1-.2.05-.39-.03-.54-.08-.15-.71-1.71-.97-2.34-.25-.61-.51-.52-.71-.53h-.61c-.21 0-.54.08-.82.39-.28.3-1.07 1.04-1.07 2.54s1.1 2.95 1.25 3.16c.16.2 2.17 3.32 5.26 4.66.73.31 1.3.5 1.74.64.73.23 1.4.2 1.93.12.59-.09 1.84-.75 2.1-1.48.26-.74.26-1.37.18-1.5-.08-.14-.28-.22-.59-.37Z"/>
    </svg>
  );
}
