import { PartnerOrderDetail } from "@/components/PartnerSpace";

export default async function PartnerOrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const orderId = Number(id);
  return <PartnerOrderDetail orderId={Number.isInteger(orderId) && orderId > 0 ? orderId : 0} />;
}
