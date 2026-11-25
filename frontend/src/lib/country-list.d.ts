export type CountryRecord = { id: number; name_fr: string; code_alpha2: string };
export function countryListFromApi(value: unknown): CountryRecord[];
export function countryLoadErrorMessage(error: unknown): string;
