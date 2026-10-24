import { z } from "zod";

export const DEFAULT_API_BASE_URL = "https://priyankas-macbook-pro.tail0ff9e3.ts.net";
export const API_STORAGE_KEY = "judy-api-base-url";

export function normalizeApiBaseUrl(value: string): string {
  const parsed = z.string().trim().max(2048).url().parse(value);
  const url = new URL(parsed);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash) {
    throw new Error("Enter an HTTPS base URL without credentials, a query, or a fragment.");
  }
  // /v1 is appended once, even when pasted from an endpoint URL.
  url.pathname = url.pathname.replace(/\/+$/, "").replace(/\/v1$/, "");
  if (/\/v1\/(plugs|events)/.test(url.pathname)) throw new Error("Enter the base URL, not a plugs or events endpoint.");
  return url.toString().replace(/\/+$/, "");
}

export function apiEndpoint(baseUrl: string, path: string): string {
  return `${normalizeApiBaseUrl(baseUrl)}/v1/${path}`;
}
/**
 * The live stream address. `lastId` is the id of the last message this page has seen, or null when
 * it has seen none. Only a reconnect passes an id: a fresh page load must never ask the server to
 * replay history, or old unresolved alerts come back as if they were new.
 */
export function eventStreamUrl(baseUrl: string, lastId: string | null): string {
  const url = new URL(apiEndpoint(baseUrl, "events"));
  if (lastId !== null) url.searchParams.set("after", lastId);
  return url.toString();
}
