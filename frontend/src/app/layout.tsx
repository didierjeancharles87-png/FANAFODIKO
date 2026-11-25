import type { Metadata, Viewport } from "next";
import { PwaRegister } from "./PwaRegister";
import { WhatsAppFloating } from "@/components/WhatsAppFloating";
import "./globals.css";

export const metadata: Metadata = {
  title: "FANAFODIKO — Votre santé, plus proche",
  description: "Trouvez des professionnels de santé, pharmacies et laboratoires à Madagascar.",
  manifest: "/manifest.webmanifest",
};
export const viewport: Viewport = { themeColor: "#075b9c" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body><PwaRegister />{children}<WhatsAppFloating /></body></html>;
}
