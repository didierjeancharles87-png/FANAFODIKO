export type PromotionConditionInput = {
  code?: string;
  ends_at?: string | null;
  max_redemptions?: number | null;
  remaining_quantity?: number | null;
};

export const PROMOTION_NOTICE: string;
export const COUPON_NOTICE: string;
export function promotionBadge(promotion: object | null | undefined): string;
export function promotionDiscount(promotion: { discount_label?: string } | null | undefined): string;
export function promotionPrice(product: { price_mga?: string; effective_price_mga?: string } | null | undefined): string;
export function promotionConditions(promotion: PromotionConditionInput | null | undefined): string[];
export function couponSummary(cart: { coupon_code?: string; coupon_error?: string | null; discount_mga?: string } | null | undefined): { applied: boolean; code: string; error: string; discount: string; message: string };
export function promotionStatusLabel(status: string): string;
export function canRequestPromotionRemoval(promotion: { status?: string } | null | undefined): boolean;
export function canEditPromotion(promotion: { status?: string } | null | undefined): boolean;
export function toDateTimeLocal(value: string | null | undefined): string;
export function fromDateTimeLocal(value: string): string;
