import { PartnerImages } from "@/components/PartnerSpace";

export default async function PartnerImagesPage({ searchParams }: { searchParams: Promise<{ product?: string }> }) {
  const params = await searchParams;
  const requested = Number(params.product);
  const initialProductId = Number.isInteger(requested) && requested > 0 ? requested : undefined;
  return <PartnerImages initialProductId={initialProductId} />;
}
