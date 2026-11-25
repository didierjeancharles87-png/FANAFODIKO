export type MarketplaceType = "medicine" | "equipment";
export type CatalogSeller = { id: number; kind: string; kind_label: string; name: string; country: string; region: string; city: string; verified: boolean };
export type PromotionSummary = {
  id: number; code: string; title: string; product: number; product_title: string;
  discount_label: string; original_price_mga: string; promotional_price_mga: string; status: string;
};
export type CatalogProduct = {
  id: number; product_type: MarketplaceType; product_type_label: string; title: string; slug: string; brand: string; description: string;
  image_url: string | null; seller: CatalogSeller; price_mga: string; effective_price_mga?: string; promotion?: PromotionSummary | null; availability: string;
  is_orderable: boolean; orderability_reason: string | null; is_sponsored: boolean;
  price_updated_at: string; availability_updated_at: string; updated_at: string; active_ingredient: string; dosage: string;
  pharmaceutical_form: string; packaging: string; requires_prescription: boolean; equipment_category: string;
  equipment_category_label: string; model_name: string; technical_specifications: Record<string, string | number | boolean>;
  warranty: string;
};
export const marketplaceTypes: Array<{id: MarketplaceType; title: string; href: string; description: string}>;
export function formatMGA(value: string | number): string;
export function formatMarketplaceDate(value: string | null | undefined): string;
export function availabilityLabel(value: string): string;
export function catalogDetailHref(product: Pick<CatalogProduct, "product_type" | "slug">): string;
