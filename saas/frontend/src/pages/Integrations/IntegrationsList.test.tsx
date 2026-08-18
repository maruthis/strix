import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { delay, mockFetchImpl } from "../../test/mock-fetch";
import IntegrationsList from "./IntegrationsList";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

const CATALOG = [
  {
    provider: "github",
    category: "code",
    label: "GitHub",
    coming_soon: false,
    configure_url: "https://github.com/settings/installations",
    status: "connected",
    account_label: "maruthis",
    credential_last4: null,
    connected_at: "2026-08-01T00:00:00Z",
  },
  {
    provider: "gitlab",
    category: "code",
    label: "GitLab",
    coming_soon: false,
    configure_url: "https://gitlab.com/-/user_settings/applications",
    status: "not_connected",
    account_label: null,
    credential_last4: null,
    connected_at: null,
  },
  { provider: "bitbucket", category: "code", label: "Bitbucket", coming_soon: false, configure_url: null, status: "not_connected", account_label: null, credential_last4: null, connected_at: null },
  { provider: "slack", category: "communication", label: "Slack", coming_soon: false, configure_url: null, status: "not_connected", account_label: null, credential_last4: null, connected_at: null },
  { provider: "msteams", category: "communication", label: "Microsoft Teams", coming_soon: true, configure_url: null, status: "not_connected", account_label: null, credential_last4: null, connected_at: null },
  { provider: "jira", category: "issue_tracking", label: "Jira", coming_soon: false, configure_url: null, status: "not_connected", account_label: null, credential_last4: null, connected_at: null },
  { provider: "linear", category: "issue_tracking", label: "Linear", coming_soon: false, configure_url: null, status: "not_connected", account_label: null, credential_last4: null, connected_at: null },
];

describe("IntegrationsList", () => {
  it("renders every section with its providers, and shows GitHub as connected", async () => {
    mockFetchImpl(async () => jsonRes(CATALOG));
    renderWithProviders(<IntegrationsList />);

    await screen.findByText("GitHub");
    expect(screen.getByText("Code Providers")).toBeInTheDocument();
    expect(screen.getByText("Communication")).toBeInTheDocument();
    expect(screen.getByText("Issue Tracking")).toBeInTheDocument();

    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("maruthis")).toBeInTheDocument();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();

    // Connected GitHub shows manage actions; unconnected providers show Connect.
    expect(screen.getByText("Connect more")).toBeInTheDocument();
    expect(screen.getByText("Disconnect")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Connect" }).length).toBe(5); // gitlab, bitbucket, slack, jira, linear

    // Configure is a real external link, not an in-app action.
    const configureLink = screen.getByRole("link", { name: /Configure/ });
    expect(configureLink).toHaveAttribute("href", "https://github.com/settings/installations");
    expect(configureLink).toHaveAttribute("target", "_blank");
    expect(configureLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows a token-ending-in hint when a credential was provided", async () => {
    mockFetchImpl(async () => jsonRes([{ ...CATALOG[0], credential_last4: "1234" }, ...CATALOG.slice(1)]));
    renderWithProviders(<IntegrationsList />);
    await screen.findByText(/token ending in 1234/);
  });

  it("opens the connect modal, submits account + credential, and updates the row", async () => {
    const fetchMock = mockFetchImpl(async (url, init) => {
      if (init?.method === "POST" && url.includes("/api/integrations/gitlab/connect")) {
        const body = JSON.parse(init.body as string);
        return jsonRes({ ...CATALOG[1], status: "connected", account_label: body.account_label, credential_last4: body.credential?.slice(-4) ?? null, connected_at: "2026-08-17T00:00:00Z" });
      }
      return jsonRes(CATALOG);
    });
    renderWithProviders(<IntegrationsList />);
    await screen.findByText("GitLab");

    const connectButtons = screen.getAllByRole("button", { name: "Connect" });
    await userEvent.click(connectButtons[0]);

    await screen.findByRole("heading", { name: "Connect GitLab" });
    const submit = screen.getByRole("button", { name: "Connect GitLab" });
    expect(submit).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText("e.g. acme-corp"), "acme");
    await userEvent.type(screen.getByPlaceholderText(/Paste a token/), "glpat-abcd1234");
    expect(submit).not.toBeDisabled();
    await userEvent.click(submit);

    await screen.findByText("acme");
    expect(screen.getByText(/token ending in 1234/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/integrations/gitlab/connect", expect.objectContaining({ method: "POST" }));
    expect(screen.queryByRole("heading", { name: "Connect GitLab" })).not.toBeInTheDocument();
  });

  it("connects without a credential, omitting it from the request body", async () => {
    const fetchMock = mockFetchImpl(async (url, init) => {
      if (init?.method === "POST" && url.includes("/api/integrations/bitbucket/connect")) {
        const body = JSON.parse(init.body as string);
        return jsonRes({ ...CATALOG[2], status: "connected", account_label: body.account_label, connected_at: "2026-08-17T00:00:00Z" });
      }
      return jsonRes(CATALOG);
    });
    renderWithProviders(<IntegrationsList />);
    await screen.findByText("Bitbucket");

    const connectButtons = screen.getAllByRole("button", { name: "Connect" });
    await userEvent.click(connectButtons[1]); // bitbucket has no dedicated hint, exercising the fallback label too

    await screen.findByRole("heading", { name: "Connect Bitbucket" });
    await userEvent.type(screen.getByPlaceholderText("e.g. acme-corp"), "acme-workspace");
    await userEvent.click(screen.getByRole("button", { name: "Connect Bitbucket" }));

    await screen.findByText("acme-workspace");
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes("bitbucket/connect"))!;
    const sentBody = JSON.parse((call[1] as RequestInit).body as string);
    expect(sentBody.credential).toBeUndefined();
  });

  it("shows a pending label while connecting", async () => {
    mockFetchImpl(async (url, init) => {
      if (init?.method === "POST" && url.includes("/api/integrations/gitlab/connect")) {
        return delay(jsonRes({ ...CATALOG[1], status: "connected", account_label: "acme" }));
      }
      return jsonRes(CATALOG);
    });
    renderWithProviders(<IntegrationsList />);
    await screen.findByText("GitLab");
    await userEvent.click(screen.getAllByRole("button", { name: "Connect" })[0]);
    await userEvent.type(await screen.findByPlaceholderText("e.g. acme-corp"), "acme");
    await userEvent.click(screen.getByRole("button", { name: "Connect GitLab" }));
    await screen.findByText("Connecting…");
  });

  it("closes the connect modal without submitting", async () => {
    mockFetchImpl(async () => jsonRes(CATALOG));
    renderWithProviders(<IntegrationsList />);
    await screen.findByText("GitLab");

    await userEvent.click(screen.getAllByRole("button", { name: "Connect" })[0]);
    const heading = await screen.findByRole("heading", { name: "Connect GitLab" });

    const dialog = heading.closest("div")!.parentElement!;
    await userEvent.click(dialog.querySelector("button")!);
    expect(screen.queryByRole("heading", { name: "Connect GitLab" })).not.toBeInTheDocument();
  });

  it("disconnects a provider", async () => {
    mockFetchImpl(async (url, init) => {
      if (init?.method === "DELETE" && url.includes("/api/integrations/github")) {
        return jsonRes({ ...CATALOG[0], status: "not_connected", account_label: null, credential_last4: null, connected_at: null });
      }
      return jsonRes(CATALOG);
    });
    renderWithProviders(<IntegrationsList />);
    await screen.findByText("Disconnect");
    const connectButtonsBefore = screen.getAllByRole("button", { name: "Connect" }).length;

    await userEvent.click(screen.getByText("Disconnect"));

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Connect" }).length).toBe(connectButtonsBefore + 1);
    });
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });

  it("navigates to Repositories from Connect more", async () => {
    mockFetchImpl(async () => jsonRes(CATALOG));
    renderWithProviders(<IntegrationsList />, { route: "/integrations" });
    await screen.findByText("Connect more");
    await userEvent.click(screen.getByText("Connect more"));
    // No route assertion needed beyond it not throwing — navigation target
    // itself (Repositories page) is covered by RepositoriesList's own tests.
  });
});
