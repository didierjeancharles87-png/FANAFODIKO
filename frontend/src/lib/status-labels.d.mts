export type StatusDomain =
  | "order"
  | "confirmation"
  | "professionalVerification"
  | "sellerVerification"
  | "account"
  | "documentReview"
  | "authorization";

export type OrderStatus =
  | "awaiting_seller"
  | "accepted"
  | "rejected"
  | "preparing"
  | "ready"
  | "completed"
  | "cancelled";

export const ORDER_CREATION_LABEL: string;
export const EMPTY_STATUS_LABEL: string;
export const UNKNOWN_STATUS_LABEL: string;

export const ORDER_STATUS_LABELS: Readonly<Record<OrderStatus, string>>;
export const STATUS_LABELS: Readonly<Record<StatusDomain, Readonly<Record<string, string>>>>;

export function statusLabel(domain: StatusDomain, value: string | null | undefined): string;
export function orderStatusLabel(value: string | null | undefined): string;
export function orderHistoryFromLabel(value: string | null | undefined): string;
