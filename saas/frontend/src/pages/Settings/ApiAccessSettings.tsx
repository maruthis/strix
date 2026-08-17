import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Key, Plus, Webhook as WebhookIcon } from "lucide-react";
import { api } from "../../api/client";
import type { ApiToken, Webhook } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { Modal } from "../../components/shared/Modal";
import { StatusPill } from "../../components/shared/StatusPill";
import { Button, Field, TextInput } from "../../components/shared/Form";
import { cn } from "../../lib/cn";

export default function ApiAccessSettings() {
  const [tab, setTab] = useState<"tokens" | "webhooks">("tokens");

  return (
    <div>
      <h1 className="text-xl font-semibold text-white">API Access</h1>
      <p className="mt-1 text-sm text-[#888]">Use the Strix API to programmatically run pentests, manage vulnerabilities, and receive webhooks.</p>

      <div className="my-5 inline-flex rounded-lg border border-[#2a2a2a] p-0.5">
        {(["tokens", "webhooks"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn("rounded-md px-3 py-1.5 text-sm capitalize", tab === t ? "bg-[rgba(255,255,255,0.1)] text-white" : "text-[#888]")}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "tokens" ? <TokensPanel /> : <WebhooksPanel />}
    </div>
  );
}

function TokensPanel() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);

  const { data: tokens, isLoading } = useQuery({ queryKey: ["api-tokens"], queryFn: () => api.get<ApiToken[]>("/api/settings/tokens") });

  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/api/settings/tokens/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-tokens"] }),
  });

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus size={15} /> New Token
        </Button>
      </div>

      {!isLoading && tokens?.length === 0 && <EmptyState icon={<Key size={20} />} title="No tokens found" />}

      {tokens && tokens.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-[#222]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#222] text-left text-xs uppercase tracking-wide text-[#666]">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Prefix</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} className="border-b border-[#1a1a1a] last:border-0">
                  <td className="px-4 py-3 text-white">{t.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-[#888]">{t.token_prefix}…</td>
                  <td className="px-4 py-3">
                    <StatusPill value={t.status} />
                  </td>
                  <td className="px-4 py-3">
                    {t.status === "active" && (
                      <Button variant="ghost" onClick={() => revoke.mutate(t.id)}>
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Token">
        <NewTokenForm
          onCreated={(token) => {
            setNewToken(token);
            setCreateOpen(false);
            queryClient.invalidateQueries({ queryKey: ["api-tokens"] });
          }}
        />
      </Modal>

      <Modal open={!!newToken} onClose={() => setNewToken(null)} title="Token created">
        <p className="mb-2 text-sm text-[#888]">Copy this token now — you won't be able to see it again.</p>
        <div className="break-all rounded-lg border border-[#2a2a2a] bg-black p-3 font-mono text-xs text-emerald-400">{newToken}</div>
      </Modal>
    </div>
  );
}

function NewTokenForm({ onCreated }: { onCreated: (token: string) => void }) {
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => api.post<ApiToken & { token: string }>("/api/settings/tokens", { name }),
    onSuccess: (res) => onCreated(res.token),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <Field label="Name">
        <TextInput required value={name} onChange={(e) => setName(e.target.value)} placeholder="CI token" autoFocus />
      </Field>
      <Button type="submit" className="w-full" disabled={create.isPending}>
        {create.isPending ? "Creating…" : "Create Token"}
      </Button>
    </form>
  );
}

function WebhooksPanel() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [url, setUrl] = useState("");

  const { data: webhooks, isLoading } = useQuery({ queryKey: ["webhooks"], queryFn: () => api.get<Webhook[]>("/api/settings/webhooks") });

  const create = useMutation({
    mutationFn: () => api.post("/api/settings/webhooks", { url }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      setUrl("");
      setCreateOpen(false);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/api/settings/webhooks/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus size={15} /> New Webhook
        </Button>
      </div>

      {!isLoading && webhooks?.length === 0 && <EmptyState icon={<WebhookIcon size={20} />} title="No webhooks configured" />}

      {webhooks?.map((w) => (
        <div key={w.id} className="mb-2 flex items-center justify-between rounded-xl border border-[#222] p-4">
          <div>
            <div className="font-mono text-sm text-white">{w.url}</div>
            <div className="mt-1 text-xs text-[#666]">{w.events.join(", ")}</div>
          </div>
          <Button variant="ghost" onClick={() => remove.mutate(w.id)}>
            Delete
          </Button>
        </div>
      ))}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Webhook">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Field label="Endpoint URL">
            <TextInput required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/webhooks/strix" />
          </Field>
          <Button type="submit" className="w-full" disabled={create.isPending}>
            Create Webhook
          </Button>
        </form>
      </Modal>
    </div>
  );
}
