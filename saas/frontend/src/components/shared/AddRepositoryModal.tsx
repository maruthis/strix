import { Github } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { InstallableRepo } from "../../api/types";
import { Modal } from "./Modal";
import { Button } from "./Form";
import { toast } from "./Toast";

export function AddRepositoryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: installable } = useQuery({
    queryKey: ["installable-repositories"],
    queryFn: () => api.get<InstallableRepo[]>("/api/repositories/installable"),
    enabled: open,
  });

  const add = useMutation({
    mutationFn: (repo: InstallableRepo) => api.post("/api/repositories", { full_name: repo.full_name, default_branch: repo.default_branch }),
    onSuccess: (_data, repo) => {
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      queryClient.invalidateQueries({ queryKey: ["installable-repositories"] });
      toast.success(`Added ${repo.full_name}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Add Repository" description="Repos visible to your GitHub App installation.">
      <div className="space-y-1.5">
        {installable?.length === 0 && <p className="py-6 text-center text-sm text-[#666]">No more repositories to add.</p>}
        {installable?.map((repo) => (
          <div key={repo.full_name} className="flex items-center justify-between rounded-lg border border-[#222] px-3 py-2.5">
            <div className="flex items-center gap-2 text-sm text-white">
              <Github size={15} className="text-[#888]" />
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
