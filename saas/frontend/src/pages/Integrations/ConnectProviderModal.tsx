import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Integration } from "../../api/types";
import { Modal } from "../../components/shared/Modal";
import { Button, Field, TextInput } from "../../components/shared/Form";
import { toast } from "../../components/shared/Toast";

const ACCOUNT_LABEL_HINT: Record<string, string> = {
  github: "GitHub organization or username",
  gitlab: "GitLab group or username",
  bitbucket: "Bitbucket workspace",
  slack: "Slack workspace",
  jira: "Jira site (e.g. acme.atlassian.net)",
  linear: "Linear workspace",
};

export function ConnectProviderModal({
  integration,
  onClose,
}: {
  integration: Integration | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [accountLabel, setAccountLabel] = useState("");
  const [credential, setCredential] = useState("");

  function reset() {
    setAccountLabel("");
    setCredential("");
  }

  const connect = useMutation({
    mutationFn: () =>
      api.post<Integration>(`/api/integrations/${integration!.provider}/connect`, {
        account_label: accountLabel,
        credential: credential || undefined,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData<Integration[]>(["integrations"], (prev) => prev?.map((i) => (i.provider === updated.provider ? updated : i)));
      toast.success(`${updated.label} connected`);
      reset();
      onClose();
    },
  });

  if (!integration) return null;

  return (
    <Modal
      open={!!integration}
      onClose={() => {
        reset();
        onClose();
      }}
      title={`Connect ${integration.label}`}
      description={`Provide the account and credentials Strix should use to connect to ${integration.label}.`}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          connect.mutate();
        }}
      >
        <Field label={ACCOUNT_LABEL_HINT[integration.provider] ?? "Account name"}>
          <TextInput
            autoFocus
            required
            value={accountLabel}
            onChange={(e) => setAccountLabel(e.target.value)}
            placeholder="e.g. acme-corp"
          />
        </Field>
        <Field label="Personal access token (optional)">
          <TextInput
            type="password"
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
            placeholder="Paste a token to authenticate as this account"
          />
        </Field>
        <p className="mb-4 text-xs text-[#666]">
          Tokens are never stored in full — only the last 4 characters are kept, for display purposes.
        </p>
        <Button type="submit" className="w-full" disabled={!accountLabel.trim() || connect.isPending}>
          {connect.isPending ? "Connecting…" : `Connect ${integration.label}`}
        </Button>
      </form>
    </Modal>
  );
}
