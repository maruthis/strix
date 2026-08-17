import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { AuditLogEntry } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { formatDate } from "../../lib/format";
import { ScrollText } from "lucide-react";

export default function AuditLogsSettings() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => api.get<AuditLogEntry[]>("/api/settings/audit-logs"),
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-white">Audit Logs</h1>
      <p className="mb-6 text-sm text-[#888]">A record of actions taken across this organization.</p>

      {!isLoading && entries?.length === 0 && <EmptyState icon={<ScrollText size={20} />} title="No activity yet" />}

      {entries && entries.length > 0 && (
        <div className="space-y-1">
          {entries.map((e) => (
            <div key={e.id} className="flex items-center justify-between border-b border-[#1a1a1a] py-2.5 text-sm">
              <div>
                <span className="text-white">{e.actor_email}</span>{" "}
                <span className="text-[#888]">{e.action.replace(/\./g, " ").replace(/_/g, " ")}</span>{" "}
                <span className="text-[#aaa]">{e.target}</span>
              </div>
              <span className="text-xs text-[#555]">{formatDate(e.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
