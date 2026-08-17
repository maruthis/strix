import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { api } from "../../api/client";
import type { Issue, IssueStatus } from "../../api/types";
import { StatusPill } from "../../components/shared/StatusPill";
import { Select } from "../../components/shared/Form";
import { formatDate } from "../../lib/format";

const STATUS_OPTIONS: { value: IssueStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "snoozed", label: "Snoozed" },
  { value: "fixed", label: "Fixed" },
  { value: "ignored", label: "Ignored" },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div className="mb-5">
      <h3 className="mb-1.5 text-sm font-medium text-white">{title}</h3>
      <div className="whitespace-pre-wrap text-sm leading-relaxed text-[#aaa]">{children}</div>
    </div>
  );
}

export default function IssueDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: issue } = useQuery({
    queryKey: ["issue", id],
    queryFn: () => api.get<Issue>(`/api/issues/${id}`),
  });

  const updateStatus = useMutation({
    mutationFn: (status: IssueStatus) => api.patch<Issue>(`/api/issues/${id}/status`, { status }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["issue", id], updated);
      queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });

  if (!issue) return null;

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => navigate(-1)} className="mb-4 flex items-center gap-1.5 text-sm text-[#888] hover:text-white">
        <ArrowLeft size={14} /> Back
      </button>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <StatusPill value={issue.severity} />
            {issue.cvss !== null && <span className="text-xs text-[#666]">CVSS {issue.cvss.toFixed(1)}</span>}
          </div>
          <h1 className="text-lg font-semibold text-white">{issue.title}</h1>
          <div className="mt-1 text-xs text-[#666]">
            {issue.target} {issue.endpoint && `· ${issue.endpoint}`} · found {formatDate(issue.created_at)}
          </div>
        </div>
        <Select
          value={issue.status}
          onChange={(v) => updateStatus.mutate(v as IssueStatus)}
          options={STATUS_OPTIONS}
        />
      </div>

      <div className="rounded-xl border border-[#222] bg-[rgba(255,255,255,0.02)] p-6">
        <Section title="Description">{issue.description}</Section>
        <Section title="Technical analysis">{issue.technical_analysis}</Section>
        <Section title="Proof of concept">{issue.poc_description}</Section>
        <Section title="Remediation">{issue.remediation_steps}</Section>
        <div className="text-xs text-[#555]">Fix effort: {issue.fix_effort}</div>
      </div>
    </div>
  );
}
