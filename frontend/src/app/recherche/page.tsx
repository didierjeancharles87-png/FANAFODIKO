import { PublicNavigation } from "@/components/PublicNavigation";
import { GlobalMarketplaceSearch } from "@/components/MarketplacePublic";

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  return <><PublicNavigation /><GlobalMarketplaceSearch initialQuery={q} /></>;
}
