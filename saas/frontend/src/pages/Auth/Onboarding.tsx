import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { OrganizationOut } from "../../api/types";
import { useSession } from "../../store/session";
import { Button, TextInput } from "../../components/shared/Form";

export default function Onboarding() {
  const navigate = useNavigate();
  const refresh = useSession((s) => s.refresh);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  async function createOrg(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const org = await api.post<OrganizationOut>("/api/orgs", { name });
      await refresh();
      await api.post("/api/auth/switch-org", { org_id: org.id });
      await refresh();
      navigate("/dashboard");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-black px-4">
      <form onSubmit={createOrg} className="w-full max-w-sm space-y-3">
        <h1 className="mb-1 text-lg font-semibold text-white">Create your organization</h1>
        <p className="mb-4 text-sm text-[#888]">This is the workspace your team will run pentests from.</p>
        <TextInput placeholder="Acme Inc" required value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "Creating…" : "Create organization"}
        </Button>
      </form>
    </div>
  );
}
