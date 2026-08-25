import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { operatorApi } from "../api/operator";
import type { Capabilities } from "../types/operator";

const Context = createContext<{ capabilities?: Capabilities; loading: boolean; offline: boolean }>({ loading: true, offline: false });
export function FeatureProvider({ children }: { children: ReactNode }) {
  const query = useQuery({ queryKey: ["capabilities"], queryFn: operatorApi.capabilities, retry: 2, staleTime: 60_000 });
  return <Context.Provider value={{ capabilities: query.data, loading: query.isLoading, offline: query.isError }}>{children}</Context.Provider>;
}
export function useFeatures() { return useContext(Context); }
