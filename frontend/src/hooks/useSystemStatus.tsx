import { createContext, useContext, type ReactNode } from "react";
import { useApi } from "./useApi";
import type { SystemStatus } from "@/types";

const Ctx = createContext<{ status: SystemStatus | null; reload: () => void }>({ status: null, reload: () => {} });

export function SystemStatusProvider({ children }: { children: ReactNode }) {
  const { data, reload } = useApi<SystemStatus>("/api/system/status");
  return <Ctx.Provider value={{ status: data, reload: () => reload(true) }}>{children}</Ctx.Provider>;
}

export const useSystemStatus = () => useContext(Ctx);
