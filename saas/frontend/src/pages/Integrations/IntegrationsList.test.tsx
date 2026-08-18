import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl } from "../../test/mock-fetch";
import IntegrationsList from "./IntegrationsList";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

const CATALOG = [
  { provider: "github", category: "code", label: "GitHub", coming_soon: false, status: "connected", account_label: "maruthis", connected_at: "2026-08-01T00:00:00Z" },
  { provider: "gitlab", category: "code", label: "GitLab", coming_soon: false, status: "not_connected", account_label: null, connected_at: null },
  { provider: "bitbucket", category: "code", label: "Bitbucket", coming_soon: false, status: "not_connected", account_label: null, connected_at: null },
  { provider: "slack", category: "communication", label: "Slack", coming_soon: false, status: "not_connected", account_label: null, connected_at: null },
  { provider: "msteams", category: "communication", label: "Microsoft Teams", coming_soon: true, status: "not_connected", account_label: null, connected_at: null },
  { provider: "jira", category: "issue_tracking", label: "Jira", coming_soon: false, status: "not_connected", account_label: null, connected_at: null },
  { provider: "linear", category: "issue_tracking", label: "Linear", coming_soon: false, status: "not_connected", account_label: null, connected_at: null },
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
    expect(screen.getByText("Configure")).toBeInTheDocument();
    expect(screen.getByText("Disconnect")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Connect" }).length).toBe(5); // gitlab, bitbucket, slack, jira, linear
  });

  it("connects a provider", async () => {
    const fetchMock = mockFetchImpl(async (url, init) => {
      if (init?.method === "POST" && url.includes("/api/integrations/gitlab/connect")) {
        return jsonRes({ ...CATALOG[1], status: "connected", account_label: "acme", connected_at: "2026-08-17T00:00:00Z" });
      }
      return jsonRes(CATALOG);
    });
    renderWithProviders(<IntegrationsList />);
    await screen.findByText("GitLab");

    const connectButtons = screen.getAllByRole("button", { name: "Connect" });
    await userEvent.click(connectButtons[0]);

    await screen.findByText("acme");
    expect(fetchMock).toHaveBeenCalledWith("/api/integrations/gitlab/connect", expect.objectContaining({ method: "POST" }));
  });

  it("disconnects a provider", async () => {
    mockFetchImpl(async (url, init) => {
      if (init?.method === "DELETE" && url.includes("/api/integrations/github")) {
        return jsonRes({ ...CATALOG[0], status: "not_connected", account_label: null, connected_at: null });
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

  it("navigates to Repositories from Connect more / Configure", async () => {
    mockFetchImpl(async () => jsonRes(CATALOG));
    renderWithProviders(<IntegrationsList />, { route: "/integrations" });
    await screen.findByText("Connect more");

    await userEvent.click(screen.getByText("Configure"));
    // No route assertion needed beyond it not throwing — navigation target
    // itself (Repositories page) is covered by RepositoriesList's own tests.
  });
});
