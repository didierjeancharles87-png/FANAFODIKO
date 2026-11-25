export type CategoryCode = "pharmacy" | "doctor" | "dentist" | "laboratory" | "delivery_courier" | "delivery_company";
export type MedicalVisual = "consultation" | "pharmacy" | "laboratory" | "dentist" | "specialists";
export type CategoryIcon = "pharmacy" | "doctor" | "dentist" | "laboratory" | "courier" | "company";

export const medicalSlides: readonly {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  actionLabel: string;
  categoryCode: CategoryCode;
  visual: MedicalVisual;
  image: string;
  photographer: string;
}[];

export const professionalCategories: readonly {
  code: CategoryCode;
  title: string;
  icon: CategoryIcon;
  description: string;
  detail: string;
}[];

export function nextSlideIndex(index: number, total: number): number;
export function previousSlideIndex(index: number, total: number): number;
export function slideIndexForKey(key: string, index: number, total: number): number | null;
