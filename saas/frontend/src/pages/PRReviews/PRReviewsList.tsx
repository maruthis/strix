import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitPullRequest, Settings as SettingsIcon, X } from "lucide-react";
import { api } from "../../api/client";
import type { PRReview, PRReviewsResponse, PRReviewSettings, PRReviewStatus, Repository, Severity } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { Modal } from "../../components/shared/Modal";
import { StatusPill } from "../../components/shared/StatusPill";
import { Tabs, FilterBar } from "../../components/shared/FilterBar";
import { Button, Field, Select, TextInput, Toggle } from "../../components/shared/Form";
import { ViewToggle, type ViewMode } from "../../components/shared/ViewToggle";
import { Board } from "../../components/shared/Board";
import { toast } from "../../components/shared/Toast";
import { timeAgo } from "../../lib/format";

const TABS = [
  { key: "all", label: "All" },
  { key: "awaiting_merge", label: "Awaiting Merge" },
  { key: "needs_attention", label: "Needs Attention" },
  { key: "merged_with_open_findings", label: "Merged with Open Findings" },
  { key: "passed", label: "Passed" },
];

const BOARD_COLUMNS: { key: PRReviewStatus; label: string }[] = [
  { key: "awaiting_merge", label: "Awaiting Merge" },
  { key: "needs_attention", label: "Needs Attention" },
  { key: "merged_with_open_findings", label: "Merged with Open Findings" },
  { key: "passed", label: "Passed" },
];

export default function PRReviewsList() {
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<ViewMode>("list");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);

  // Board mode always shows every status grouped into columns, so it ignores
  // the status tab (which only applies to list mode).
  const effectiveStatus = view === "board" ? "all" : status;
  const { data, isLoading } = useQuery({
    queryKey: ["pr-reviews", effectiveStatus, search],
    queryFn: () =>
      api.get<PRReviewsResponse>(
        `/api/pr-reviews?${effectiveStatus !== "all" ? `status_filter=${effectiveStatus}&` : ""}${search ? `search=${encodeURIComponent(search)}` : ""}`
      ),
  });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">PR Reviews</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setSettingsOpen(true)}>
            <SettingsIcon size={15} /> Settings
          </Button>
          <Button onClick={() => setReviewOpen(true)}>Review a Pull Request</Button>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-2 rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-sm text-blue-300">
        Tip — Tag <code className="rounded bg-blue-500/10 px-1">@strix</code> on any pull request to run a security review.
      </div>

      {view === "list" && <Tabs tabs={TABS.map((t) => ({ ...t, count: data?.counts?.[t.key] ?? 0 }))} active={status} onChange={setStatus} />}

      <FilterBar search={search} onSearch={setSearch} placeholder="Search repository, title, or PR number">
        <ViewToggle view={view} onChange={setView} />
      </FilterBar>

      {!isLoading && data?.items.length === 0 && (
        <EmptyState icon={<GitPullRequest size={20} />} title="No PR reviews" description="Tag @strix on any pull request to run a security review." />
      )}

      {data && data.items.length > 0 && view === "list" && (
        <div className="space-y-2">
          {data.items.map((r) => (
            <PRReviewRow key={r.id} review={r} />
          ))}
        </div>
      )}

      {data && data.items.length > 0 && view === "board" && (
        <Board
          columns={BOARD_COLUMNS.map((col) => ({ ...col, items: data.items.filter((r) => r.status === col.key) }))}
          renderCard={(r) => <PRReviewCard review={r} />}
        />
      )}

      <PRReviewSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <TriggerReviewModal open={reviewOpen} onClose={() => setReviewOpen(false)} />
    </div>
  );
}

function PRReviewRow({ review: r }: { review: PRReview }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-[#222] bg-[rgba(255,255,255,0.02)] p-4">
      <div>
        <div className="text-sm text-white">
          {r.repository_full_name} <span className="text-[#666]">#{r.pr_number}</span> — {r.title}
        </div>
        <div className="mt-1 text-xs text-[#666]">
          by {r.author} · {timeAgo(r.updated_at)} · {r.findings_count} finding(s)
        </div>
      </div>
      <StatusPill value={r.status} />
    </div>
  );
}

function PRReviewCard({ review: r }: { review: PRReview }) {
  return (
    <div className="rounded-lg border border-[#222] bg-[rgba(255,255,255,0.02)] p-3">
      <div className="mb-1 text-sm text-white">
        {r.repository_full_name} <span className="text-[#666]">#{r.pr_number}</span>
      </div>
      <div className="mb-2 text-xs text-[#888]">{r.title}</div>
      <div className="flex items-center justify-between text-[10px] text-[#666]">
        <span>{r.author}</span>
        <span>{r.findings_count} finding(s)</span>
      </div>
    </div>
  );
}

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

function PRReviewSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: settings } = useQuery({
    queryKey: ["pr-review-settings"],
    queryFn: () => api.get<PRReviewSettings>("/api/pr-reviews/settings"),
    enabled: open,
  });

  const update = useMutation({
    mutationFn: (patch: Partial<PRReviewSettings>) => api.patch<PRReviewSettings>("/api/pr-reviews/settings", patch),
    onSuccess: (updated) => queryClient.setQueryData(["pr-review-settings"], updated),
  });

  if (!settings) return <Modal open={open} onClose={onClose} title="PR Review Settings" children={null} />;

  return (
    <Modal open={open} onClose={onClose} title="PR Review Settings" description="Configure how reviews are triggered and billed." width="max-w-xl">
      <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
        <ToggleRow label="Re-review on push" checked={settings.rereview_on_push} onChange={(v) => update.mutate({ rereview_on_push: v })} />

        <TagListField
          label="Target branches"
          placeholder="branch or pattern…"
          values={settings.target_branches}
          onChange={(target_branches) => update.mutate({ target_branches })}
        />

        <ToggleRow label="Approve clean PRs" checked={settings.approve_clean_prs} onChange={(v) => update.mutate({ approve_clean_prs: v })} />

        <ToggleRow
          label="Block PRs on findings"
          checked={settings.block_prs_on_findings}
          onChange={(v) => update.mutate({ block_prs_on_findings: v })}
        />
        {settings.block_prs_on_findings && (
          <div className="-mt-3 flex gap-2 pl-1">
            {SEVERITIES.map((s) => {
              const active = settings.blocking_severities.includes(s);
              return (
                <button
                  key={s}
                  onClick={() =>
                    update.mutate({
                      blocking_severities: active
                        ? settings.blocking_severities.filter((x) => x !== s)
                        : [...settings.blocking_severities, s],
                    })
                  }
                  className={`rounded-full border px-3 py-1 text-xs capitalize transition-colors ${
                    active ? "border-white/40 bg-white/10 text-white" : "border-[#2a2a2a] text-[#666]"
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        )}

        <ToggleRow
          label="Exclude bot accounts"
          checked={settings.exclude_bot_accounts}
          onChange={(v) => update.mutate({ exclude_bot_accounts: v })}
        />
        <TagListField
          label="Excluded usernames"
          placeholder="username…"
          values={settings.excluded_usernames}
          onChange={(excluded_usernames) => update.mutate({ excluded_usernames })}
        />

        <ToggleRow
          label="Allow overage reviews"
          checked={settings.allow_overage_reviews}
          onChange={(v) => update.mutate({ allow_overage_reviews: v })}
        />

        <Field label="Review cap per developer">
          <div className="flex items-center gap-2">
            <TextInput
              type="number"
              placeholder="No cap"
              defaultValue={settings.review_cap_per_dev ?? ""}
              onBlur={(e) => update.mutate({ review_cap_per_dev: e.target.value ? Number(e.target.value) : null })}
              className="w-28"
            />
            <span className="text-xs text-[#666]">reviews / dev / {settings.review_cap_period}</span>
          </div>
        </Field>
      </div>
    </Modal>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-white">{label}</span>
      <Toggle checked={checked} onChange={onChange} />
    </div>
  );
}

function TagListField({
  label,
  placeholder,
  values,
  onChange,
}: {
  label: string;
  placeholder: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const value = draft.trim();
    if (value && !values.includes(value)) onChange([...values, value]);
    setDraft("");
  }

  return (
    <Field label={label}>
      <div className="flex gap-2">
        <TextInput
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
        />
        <Button type="button" variant="secondary" onClick={add}>
          + Add
        </Button>
      </div>
      {values.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((v) => (
            <span key={v} className="flex items-center gap-1 rounded-full border border-[#2a2a2a] px-2.5 py-1 text-xs text-[#ccc]">
              {v}
              <button type="button" onClick={() => onChange(values.filter((x) => x !== v))} className="text-[#666] hover:text-white">
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
    </Field>
  );
}

function TriggerReviewModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: repos } = useQuery({ queryKey: ["repositories"], queryFn: () => api.get<Repository[]>("/api/repositories"), enabled: open });
  const [repositoryId, setRepositoryId] = useState("");
  const [prNumber, setPrNumber] = useState("");
  const [title, setTitle] = useState("");

  const trigger = useMutation({
    mutationFn: () => api.post<PRReview>("/api/pr-reviews", { repository_id: repositoryId, pr_number: Number(prNumber), title }),
    onSuccess: (review) => {
      queryClient.invalidateQueries({ queryKey: ["pr-reviews"] });
      onClose();
      toast.success(`Review ${review.status === "passed" ? "passed" : `found ${review.findings_count} finding(s)`}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Review a Pull Request">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          trigger.mutate();
        }}
      >
        <Field label="Repository">
          <Select
            value={repositoryId}
            onChange={setRepositoryId}
            options={[{ value: "", label: "Select a repository…" }, ...(repos ?? []).map((r) => ({ value: r.id, label: r.full_name }))]}
            className="w-full"
          />
        </Field>
        <Field label="PR number">
          <TextInput type="number" required value={prNumber} onChange={(e) => setPrNumber(e.target.value)} placeholder="42" />
        </Field>
        <Field label="PR title">
          <TextInput required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add wallet withdraw endpoint" />
        </Field>
        <Button type="submit" className="w-full" disabled={!repositoryId || trigger.isPending}>
          {trigger.isPending ? "Reviewing…" : "Run review"}
        </Button>
      </form>
    </Modal>
  );
}
