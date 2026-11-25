import { PartnerProductEditor } from "@/components/PartnerSpace";

export default async function PartnerProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const productId = Number(id);
  return <PartnerProductEditor productId={Number.isInteger(productId) && productId > 0 ? productId : 0} />;
}
