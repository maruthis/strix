import { useState } from "react";
import { Link } from "react-router-dom";
import { Github, Gitlab } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { InstallableRepo } from "../../api/types";
import { Modal } from "./Modal";
import { Button } from "./Form";
import { toast } from "./Toast";
import { cn } from "../../lib/cn";

type Provider = "github" | "gitlab";

const PROVIDER_ICON = { github: Github, gitlab: Gitlab };
const PROVIDER_LABEL = { github: "GitHub", gitlab: "GitLab" };

export function AddRepositoryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<Provider>("github");
  const Icon = PROVIDER_ICON[provider];

  const { data: installable, isLoading } = useQuery({
    queryKey: ["installable-repositories", provider],
    queryFn: () => api.get<InstallableRepo[]>(`/api/repositories/installable?provider=${provider}`),
    enabled: open,
  });

  const add = useMutation({
    mutationFn: (repo: InstallableRepo) => api.post("/api/repositories", { full_name: repo.full_name, default_branch: repo.default_branch, provider }),
    onSuccess: (_data, repo) => {
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      queryClient.invalidateQueries({ queryKey: ["installable-repositories", provider] });
      toast.success(`Added ${repo.full_name}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Add Repository" description="Repos visible through your connected GitHub or GitLab account.">
      <div className="mb-4 flex gap-1.5 rounded-lg border border-[#2a2a2a] p-1">
        {(["github", "gitlab"] as const).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setProvider(p)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-sm transition-colors",
              provider === p ? "bg-white text-black" : "text-[#888] hover:text-white"
            )}
          >
            {p === "github" ? <Github size={14} /> : <Gitlab size={14} />}
            {PROVIDER_LABEL[p]}
          </button>
        ))}
      </div>

      <div className="space-y-1.5">
        {!isLoading && installable?.length === 0 && (
          <p className="py-6 text-center text-sm text-[#666]">
            No more repositories to add. Connect {PROVIDER_LABEL[provider]} (or add more repos to it) from{" "}
            <Link to="/integrations" onClick={onClose} className="text-white underline underline-offset-2">
              Integrations
            </Link>
            .
          </p>
        )}
        {installable?.map((repo) => (
          <div key={repo.full_name} className="flex items-center justify-between rounded-lg border border-[#222] px-3 py-2.5">
            <div className="flex items-center gap-2 text-sm text-white">
              <Icon size={15} className="text-[#888]" />
              {repo.full_name}
              {repo.private && <span className="rounded-full border border-[#333] px-1.5 py-0.5 text-[10px] text-[#888]">Private</span>}
            </div>
            <Button variant="secondary" onClick={() => add.mutate(repo)} disabled={add.isPending}>
              Add
            </Button>
          </div>
        ))}
      </div>
    </Modal>
  );
}
