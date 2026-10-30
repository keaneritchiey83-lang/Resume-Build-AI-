export const API_URL =
  import.meta.env.VITE_API_URL ?? "";

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const method = (options.method ?? "GET").toUpperCase();
  const csrf = document.cookie
    .split("; ")
    .find((item) => item.startsWith("career_csrf="))
    ?.split("=")
    .slice(1)
    .join("=");

  if (
    csrf &&
    ["POST", "PUT", "PATCH", "DELETE"].includes(method) &&
    !headers.has("Authorization")
  ) {
    headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;

    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {
      // The fallback status message is sufficient.
    }

    throw new Error(String(detail));
  }

  return response.json() as Promise<T>;
}
