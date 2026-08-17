import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ListChecks } from "lucide-react";
import { api } from "../../api/client";
import type { IssuesResponse } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { StatusPill } from "../../components/shared/StatusPill";
import { FilterBar, Tabs } from "../../components/shared/FilterBar";
import { timeAgo } from "../../lib/format";

const STATUS_TABS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "in_progress", label: "In Progress" },
  { key: "snoozed", label: "Snoozed" },
  { key: "fixed", label: "Fixed" },
  { key: "ignored", label: "Ignored" },
];

export default function IssuesList() {
  const [status, setStatus] = useState("open");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["issues", status],
    queryFn: () =>
      api.get<IssuesResponse>(`/api/issues${status !== "all" ? `?status_filter=${status}` : ""}`),
  });

  const items = (data?.items ?? []).filter((i) => i.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-white">Issues</h1>

      <div className="mb-6 flex gap-8">
        {(["critical", "high", "medium", "low"] as const).map((s) => (
          <div key={s}>
            <div className="text-sm capitalize text-[#888]">{s}</div>
            <div className="text-2xl font-semibold text-white">{data?.severity_counts?.[s] ?? 0}</div>
          </div>
        ))}
      </div>

      <Tabs
        tabs={STATUS_TABS.map((t) => ({ ...t, count: data?.status_counts?.[t.key] ?? 0 }))}
        active={status}
        onChange={setStatus}
      />

      <FilterBar search={search} onSearch={setSearch} placeholder="Search issues..." />

      {!isLoading && items.length === 0 && <EmptyState icon={<ListChecks size={20} />} title="No issues" />}

      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((issue) => (
            <Link
              key={issue.id}
              to={`/issues/${issue.id}`}
              className="flex items-center justify-between rounded-xl border border-[#222] bg-[rgba(255,255,255,0.02)] p-4 hover:border-[#333]"
            >
              <div>
                <div className="text-sm text-white">{issue.title}</div>
                <div className="mt-1 text-xs text-[#666]">
                  {issue.target} · {timeAgo(issue.created_at)}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill value={issue.status} />
                <StatusPill value={issue.severity} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
