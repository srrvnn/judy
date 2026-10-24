import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { API_STORAGE_KEY, DEFAULT_API_BASE_URL, normalizeApiBaseUrl } from "@/lib/api-config";

type ApiConfig = { baseUrl: string; ready: boolean; saveBaseUrl: (value: string) => void };
const ApiContext = createContext<ApiConfig | null>(null);

export function ApiConfigProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try {
      const saved = localStorage.getItem(API_STORAGE_KEY);
      if (saved) setBaseUrl(normalizeApiBaseUrl(saved));
    } catch { /* Unavailable storage or an invalid old preference uses the default. */ }
    setReady(true);
  }, []);
  const saveBaseUrl = (value: string) => {
    const normalized = normalizeApiBaseUrl(value);
    localStorage.setItem(API_STORAGE_KEY, normalized);
    setBaseUrl(normalized);
  };
  return <ApiContext.Provider value={{ baseUrl, ready, saveBaseUrl }}>{children}</ApiContext.Provider>;
}

export function useApiConfig() {
  const context = useContext(ApiContext);
  if (!context) throw new Error("API configuration provider is missing");
  return context;
}