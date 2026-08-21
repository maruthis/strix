import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, GitPullRequest, Github, Plus, Settings as SettingsIcon, X } from "lucide-react";
import { api } from "../../api/client";
import type { PRReview, PRReviewsResponse, PRReviewSettings, PRReviewStatus, Repository, RepoPullRequest, Severity } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { Modal } from "../../components/shared/Modal";
import { AddRepositoryModal } from "../../components/shared/AddRepositoryModal";
import { StatusPill } from "../../components/shared/StatusPill";
import { Tabs, FilterBar } from "../../components/shared/FilterBar";
import { Button, Field, TextInput, Toggle } from "../../components/shared/Form";
import { ViewToggle, type ViewMode } from "../../components/shared/ViewToggle";
import { Board } from "../../components/shared/Board";
import { toast } from "../../components/shared/Toast";
import { timeAgo } from "../../lib/format";
import { useDebouncedValue } from "../../lib/useDebouncedValue";

const TABS = [
  { key: "all", label: "All" },
  { key: "awaiting_merge", label: "Awaiting Merge" },
  { key: "needs_attention", label: "Needs Attention" },
  { key: "merged_with_open_findings", label: "Merged with Open Findings" },
  { key: "passed", label: "Passed" },
];

const BOARD_COLUMNS: { key: PRReviewStatus; label: string }[] = [
  { key: "running", label: "Running" },
  { key: "awaiting_merge", label: "Awaiting Merge" },
  { key: "needs_attention", label: "Needs Attention" },
  { key: "merged_with_open_findings", label: "Merged with Open Findings" },
  { key: "passed", label: "Passed" },
  { key: "failed", label: "Failed" },
];

export default function PRReviewsList() {
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<ViewMode>("list");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);

  // Board mode always shows every status grouped into columns, so it ignores
  // the status tab (which only applies to list mode).
  const effectiveStatus = view === "board" ? "all" : status;
  const debouncedSearch = useDebouncedValue(search, 300);
  const { data, isLoading } = useQuery({
    queryKey: ["pr-reviews", effectiveStatus, debouncedSearch],
    queryFn: () =>
      api.get<PRReviewsResponse>(
        `/api/pr-reviews?${effectiveStatus !== "all" ? `status_filter=${effectiveStatus}&` : ""}${debouncedSearch ? `search=${encodeURIComponent(debouncedSearch)}` : ""}`
      ),
    // A triggered review runs a real scan and starts out "running" — poll
    // so its row updates to a final status without a manual refresh.
    refetchInterval: 4000,
  });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">PR Reviews</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setSettingsOpen(true)}>
            <SettingsIcon size={15} /> Settings
          </Button>
          <Button variant="secondary" onClick={() => setConnectOpen(true)}>
            <Plus size={15} /> Connect Repository
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
      <AddRepositoryModal open={connectOpen} onClose={() => setConnectOpen(false)} />
    </div>
  );
}

// Statuses that mean the scan has actually finished — a report only exists
// once one of these is reached (mirrors app/routers/pr_reviews.py's
// _DONE_STATUSES).
const DONE_STATUSES = new Set(["awaiting_merge", "needs_attention", "merged_with_open_findings", "passed"]);

function ReportLinks({ reviewId }: { reviewId: string }) {
  return (
    <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
      <a href={`/api/pr-reviews/${reviewId}/report`} target="_blank" rel="noreferrer" title="View report" className="text-[#888] hover:text-white">
        <Eye size={16} />
      </a>
      <a href={`/api/pr-reviews/${reviewId}/report/download`} title="Download report (PDF)" className="text-[#888] hover:text-white">
        <Download size={16} />
      </a>
    </div>
  );
}

function PRReviewRow({ review: r }: { review: PRReview }) {
  const navigate = useNavigate();
  return (
    <div
      onClick={() => navigate(`/pr-reviews/${r.id}`)}
      className="flex cursor-pointer items-center justify-between rounded-xl border border-[#222] bg-[rgba(255,255,255,0.02)] p-4 hover:border-[#333]"
    >
      <div>
        <div className="text-sm text-white">
          {r.repository_full_name} <span className="text-[#666]">#{r.pr_number}</span> — {r.title}
        </div>
        <div className="mt-1 text-xs text-[#666]">
          by {r.author} · {timeAgo(r.updated_at)} · {r.status === "running" ? "scanning…" : `${r.findings_count} finding(s)`}
        </div>
        {r.status === "failed" && r.error && <div className="mt-1 text-xs text-red-400">{r.error}</div>}
      </div>
      <div className="flex items-center gap-3">
        {DONE_STATUSES.has(r.status) && <ReportLinks reviewId={r.id} />}
        <StatusPill value={r.status} />
      </div>
    </div>
  );
}

function PRReviewCard({ review: r }: { review: PRReview }) {
  const navigate = useNavigate();
  return (
    <div
      onClick={() => navigate(`/pr-reviews/${r.id}`)}
      className="cursor-pointer rounded-lg border border-[#222] bg-[rgba(255,255,255,0.02)] p-3 hover:border-[#333]"
    >
      <div className="mb-1 text-sm text-white">
        {r.repository_full_name} <span className="text-[#666]">#{r.pr_number}</span>
      </div>
      <div className="mb-2 text-xs text-[#888]">{r.title}</div>
      <div className="flex items-center justify-between text-[10px] text-[#666]">
        <span>{r.author}</span>
        <div className="flex items-center gap-2">
          {DONE_STATUSES.has(r.status) && <ReportLinks reviewId={r.id} />}
          <span>{r.status === "running" ? "scanning…" : `${r.findings_count} finding(s)`}</span>
        </div>
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
  const [repoSearch, setRepoSearch] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [manualEntry, setManualEntry] = useState(false);
  const [prNumber, setPrNumber] = useState("");
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [targetBranch, setTargetBranch] = useState("");

  const { data: pullRequests, isFetching: prsLoading } = useQuery({
    queryKey: ["repository-pull-requests", selectedRepo?.id],
    queryFn: () => api.get<RepoPullRequest[]>(`/api/repositories/${selectedRepo!.id}/pull-requests`),
    enabled: !!selectedRepo,
  });

  function reset() {
    setRepoSearch("");
    setSelectedRepo(null);
    setManualEntry(false);
    setPrNumber("");
    setTitle("");
    setAuthor("");
    setTargetBranch("");
  }

  function selectPullRequest(pr: RepoPullRequest) {
    setPrNumber(String(pr.number));
    setTitle(pr.title);
    setAuthor(pr.author);
    setTargetBranch(pr.target_branch ?? "");
    setManualEntry(true);
  }

  const trigger = useMutation({
    mutationFn: () =>
      api.post<PRReview>("/api/pr-reviews", {
        repository_id: selectedRepo!.id,
        pr_number: Number(prNumber),
        title,
        ...(author ? { author } : {}),
        ...(targetBranch ? { target_branch: targetBranch } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pr-reviews"] });
      onClose();
      reset();
      toast.success("Review queued — running a real scan now");
    },
  });

  const filteredRepos = (repos ?? []).filter((r) => r.full_name.toLowerCase().includes(repoSearch.toLowerCase()));

  if (!selectedRepo) {
    return (
      <Modal
        open={open}
        onClose={() => {
          onClose();
          reset();
        }}
        title="Review a pull request"
        description="Select a connected repository, then choose an open pull request or enter its number."
      >
        <TextInput
          autoFocus
          value={repoSearch}
          onChange={(e) => setRepoSearch(e.target.value)}
          placeholder="Search repositories"
          className="mb-3"
        />
        <div className="max-h-72 space-y-1.5 overflow-y-auto">
          {filteredRepos.length === 0 && <p className="py-6 text-center text-sm text-[#666]">No connected repositories found.</p>}
          {filteredRepos.map((repo) => (
            <button
              key={repo.id}
              type="button"
              onClick={() => setSelectedRepo(repo)}
              className="flex w-full items-center gap-2 rounded-lg border border-[#222] px-3 py-2.5 text-left text-sm text-white hover:bg-[rgba(255,255,255,0.04)]"
            >
              <Github size={15} className="text-[#888]" />
              {repo.full_name}
            </button>
          ))}
        </div>
      </Modal>
    );
  }

  // A live, credentialed GitHub/GitLab integration found open PRs/MRs — let
  // the user pick one instead of typing the number and title by hand.
  if (!manualEntry && (prsLoading || (pullRequests && pullRequests.length > 0))) {
    return (
      <Modal
        open={open}
        onClose={() => {
          onClose();
          reset();
        }}
        title="Review a pull request"
        description="Choose an open pull request, or enter its number and title manually."
      >
        <div className="mb-3 flex w-full items-center gap-2 rounded-lg border border-[#222] px-3 py-2 text-left text-sm text-white">
          <Github size={15} className="text-[#888]" />
          {selectedRepo.full_name}
          <button type="button" onClick={() => setSelectedRepo(null)} className="ml-auto text-xs text-[#666] hover:text-white">
            Change
          </button>
        </div>
        {prsLoading && <p className="py-6 text-center text-sm text-[#666]">Loading open pull requests…</p>}
        {!prsLoading && (
          <div className="max-h-72 space-y-1.5 overflow-y-auto">
            {(pullRequests ?? []).map((pr) => (
              <button
                key={pr.number}
                type="button"
                onClick={() => selectPullRequest(pr)}
                className="flex w-full items-start gap-2 rounded-lg border border-[#222] px-3 py-2.5 text-left hover:bg-[rgba(255,255,255,0.04)]"
              >
                <GitPullRequest size={15} className="mt-0.5 shrink-0 text-[#888]" />
                <div className="min-w-0">
                  <div className="truncate text-sm text-white">
                    <span className="text-[#666]">#{pr.number}</span> {pr.title}
                  </div>
                  <div className="mt-0.5 text-xs text-[#666]">by {pr.author}</div>
                </div>
              </button>
            ))}
          </div>
        )}
        {!prsLoading && (
          <button type="button" onClick={() => setManualEntry(true)} className="mt-3 text-xs text-[#888] hover:text-white">
            Can't find it? Enter the PR number manually
          </button>
        )}
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        onClose();
        reset();
      }}
      title="Review a pull request"
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          trigger.mutate();
        }}
      >
        <Field label="Repository">
          <button
            type="button"
            onClick={() => setSelectedRepo(null)}
            className="flex w-full items-center gap-2 rounded-lg border border-[#222] px-3 py-2 text-left text-sm text-white hover:bg-[rgba(255,255,255,0.04)]"
          >
            <Github size={15} className="text-[#888]" />
            {selectedRepo.full_name}
            <span className="ml-auto text-xs text-[#666]">Change</span>
          </button>
        </Field>
        {!!pullRequests?.length && (
          <button type="button" onClick={() => setManualEntry(false)} className="mb-4 -mt-2 text-xs text-[#888] hover:text-white">
            ← Pick from open pull requests instead
          </button>
        )}
        <Field label="PR number">
          <TextInput type="number" required value={prNumber} onChange={(e) => setPrNumber(e.target.value)} placeholder="42" />
        </Field>
        <Field label="PR title">
          <TextInput required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add wallet withdraw endpoint" />
        </Field>
        <Button type="submit" className="w-full" disabled={trigger.isPending}>
          {trigger.isPending ? "Reviewing…" : "Run review"}
        </Button>
      </form>
    </Modal>
  );
}
