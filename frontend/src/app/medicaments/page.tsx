import { PublicNavigation } from "@/components/PublicNavigation";
import { ProductCatalog } from "@/components/MarketplacePublic";

export default function MedicinesPage() {
  return <><PublicNavigation /><ProductCatalog productType="medicine" /></>;
}
