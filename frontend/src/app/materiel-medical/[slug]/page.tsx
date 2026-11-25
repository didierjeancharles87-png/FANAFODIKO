import { PublicNavigation } from "@/components/PublicNavigation";
import { ProductDetail } from "@/components/MarketplacePublic";

export default async function EquipmentDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <><PublicNavigation /><ProductDetail slug={slug} expectedType="equipment" /></>;
}
