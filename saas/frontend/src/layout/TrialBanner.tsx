import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Subscription } from "../api/types";
import { Button } from "../components/shared/Form";

export function TrialBanner() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["billing"],
    queryFn: () => api.get<Subscription>("/api/settings/billing"),
  });

  if (!data || data.status !== "trialing" || data.card_added) return null;

  const daysLeft = data.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(data.trial_ends_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
    : null;

  return (
    <div className="flex items-center justify-center gap-2 border-b border-[#1a1a1a] bg-[rgba(255,255,255,0.02)] px-4 py-2.5 text-sm">
      <span className="text-[#aaa]">
        Your trial ends in <span className="font-semibold text-white">{daysLeft ?? "—"} days</span>. Add a card to keep using Strix. You
        won't be charged until it ends.
      </span>
      <Button
        variant="ghost"
        className="!p-0 font-semibold text-white underline underline-offset-2"
        onClick={async () => {
          await api.post("/api/settings/billing/add-card");
          queryClient.invalidateQueries({ queryKey: ["billing"] });
        }}
      >
        Add card
      </Button>
    </div>
  );
}
