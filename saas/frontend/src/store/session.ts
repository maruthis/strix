import { create } from "zustand";
import { api } from "../api/client";
import type { MeOut } from "../api/types";

interface SessionState {
  me: MeOut | null;
  loading: boolean;
  loaded: boolean;
  refresh: () => Promise<void>;
  switchOrg: (orgId: string) => Promise<void>;
  logout: () => Promise<void>;
  setMe: (me: MeOut) => void;
}

export const useSession = create<SessionState>((set) => ({
  me: null,
  loading: false,
  loaded: false,
  setMe: (me) => set({ me, loaded: true }),
  refresh: async () => {
    set({ loading: true });
    try {
      const me = await api.get<MeOut>("/api/auth/me");
      set({ me, loading: false, loaded: true });
    } catch {
      set({ me: null, loading: false, loaded: true });
    }
  },
  switchOrg: async (orgId: string) => {
    const me = await api.post<MeOut>("/api/auth/switch-org", { org_id: orgId });
    set({ me });
  },
  logout: async () => {
    await api.post("/api/auth/logout");
    set({ me: null });
  },
}));
