import { ClientOrderLookup } from "@/components/ClientSpace";

export default async function OrderConfirmationPage({ params }: { params: Promise<{ reference: string }> }) {
  const { reference } = await params;
  return <ClientOrderLookup reference={reference} confirmed />;
}
