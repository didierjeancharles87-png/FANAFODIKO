export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

function readCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const token = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("csrftoken="));
  return token ? decodeURIComponent(token.slice("csrftoken=".length)) : undefined;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly details?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const csrfToken = ["GET", "HEAD", "OPTIONS"].includes(method) ? undefined : readCsrfToken();
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (csrfToken) headers.set("X-CSRFToken", csrfToken);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  const rawBody = await response.text();
  let body: { error?: { message?: string; details?: unknown }; detail?: string } | T;
  try {
    body = rawBody ? JSON.parse(rawBody) as typeof body : {} as T;
  } catch {
    body = {} as T;
  }
  if (!response.ok) {
    const errorBody = body as { error?: { message?: string; details?: unknown }; detail?: string };
    throw new ApiError(errorBody.error?.message ?? errorBody.detail ?? `La requête API a échoué (${response.status}).`, response.status, errorBody.error?.details);
  }

  return body as T;
}

/** Récupère le cookie CSRF puis exécute une mutation de session. */
export async function apiMutate<T>(path: string, init?: RequestInit): Promise<T> {
  await apiFetch("/v1/auth/csrf/");
  return apiFetch<T>(path, init);
}
