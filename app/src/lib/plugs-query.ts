import { queryOptions } from "@tanstack/react-query";
import { listPlugs } from "@/lib/plugs.functions";
import { DEFAULT_API_BASE_URL } from "@/lib/api-config";
import { fetchApiPlugs } from "@/lib/api-client";

export const plugsQueryFor = (baseUrl: string) => queryOptions({
  queryKey: ["plugs", baseUrl],
  queryFn: async () => {
    try {
      return baseUrl === DEFAULT_API_BASE_URL ? await listPlugs() : await fetchApiPlugs(baseUrl);
    } catch {
      return null;
    }
  },
  refetchInterval: 5000,
});
export const plugsQuery = plugsQueryFor(DEFAULT_API_BASE_URL);