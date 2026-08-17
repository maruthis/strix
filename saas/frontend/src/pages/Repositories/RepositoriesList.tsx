import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Github, Layers, Plus } from "lucide-react";
import { api } from "../../api/client";
import type { InstallableRepo, Repository } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { Modal } from "../../components/shared/Modal";
import { StatusPill } from "../../components/shared/StatusPill";
import { Button, Toggle } from "../../components/shared/Form";
import { timeAgo } from "../../lib/format";

export default function RepositoriesList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);

  const { data: repos, isLoading } = useQuery({
    queryKey: ["repositories"],
    queryFn: () => api.get<Repository[]>("/api/repositories"),
  });

  const toggleAutoReview = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/api/repositories/${id}`, { auto_review_enabled: enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["repositories"] }),
  });

  const scan = useMutation({
    mutationFn: (id: string) => api.post<{ pentest_id: string }>(`/api/repositories/${id}/scan`),
    onSuccess: (res) => navigate(`/pentests/${res.pentest_id}`),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Repositories</h1>
        <Button onClick={() => setAddOpen(true)}>
          <Plus size={15} /> Add Repository
        </Button>
      </div>

      {!isLoading && repos?.length === 0 && (
        <EmptyState icon={<Layers size={20} />} title="No repositories yet" description="Connect a repository to start scanning it." />
      )}

      {repos && repos.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-[#222]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#222] text-left text-xs uppercase tracking-wide text-[#666]">
                <th className="px-4 py-3 font-medium">Repository</th>
                <th className="px-4 py-3 font-medium">Issues</th>
                <th className="px-4 py-3 font-medium">Auto-Review</th>
                <th className="px-4 py-3 font-medium">Last Tested</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {repos.map((repo) => (
                <tr key={repo.id} className="border-b border-[#1a1a1a] last:border-0 hover:bg-[rgba(255,255,255,0.02)]">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 text-white">
                      <Github size={15} className="text-[#888]" />
                      {repo.full_name}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[#aaa]">{repo.open_issues_count || "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Toggle
                        checked={repo.auto_review_enabled}
                        onChange={(v) => toggleAutoReview.mutate({ id: repo.id, enabled: v })}
                      />
                      <StatusPill value={repo.auto_review_enabled ? "enabled" : "disabled"} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[#aaa]">{repo.last_tested_at ? timeAgo(repo.last_tested_at) : "—"}</td>
                  <td className="px-4 py-3">
                    <Button variant="secondary" onClick={() => scan.mutate(repo.id)} disabled={scan.isPending}>
                      Run scan
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AddRepositoryModal open={addOpen} onClose={() => setAddOpen(false)} />
    </div>
  );
}

function AddRepositoryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: installable } = useQuery({
    queryKey: ["installable-repositories"],
    queryFn: () => api.get<InstallableRepo[]>("/api/repositories/installable"),
    enabled: open,
  });

  const add = useMutation({
    mutationFn: (repo: InstallableRepo) => api.post("/api/repositories", { full_name: repo.full_name, default_branch: repo.default_branch }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      queryClient.invalidateQueries({ queryKey: ["installable-repositories"] });
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
