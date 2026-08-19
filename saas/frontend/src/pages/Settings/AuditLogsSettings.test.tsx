import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl } from "../../test/mock-fetch";
import AuditLogsSettings from "./AuditLogsSettings";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

describe("AuditLogsSettings", () => {
  it("shows an empty state when there's no activity", async () => {
    mockFetchImpl(async (url) => {
      if (url.includes("/api/members")) return jsonResponse([]);
      return jsonResponse({ items: [], total: 0, page: 1, page_size: 50 });
    });
    renderWithProviders(<AuditLogsSettings />);
    await screen.findByText("No activity yet");
  });

  it("renders audit log entries", async () => {
    mockFetchImpl(async (url) => {
      if (url.includes("/api/members")) return jsonResponse([]);
      return jsonResponse({
        items: [
          {
            id: "e1",
            actor_user_id: "u1",
            actor_email: "a@example.com",
            action: "org.renamed",
            target: "Acme",
            extra: {},
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
      });
    });
    renderWithProviders(<AuditLogsSettings />);
    await screen.findByText("a@example.com");
    expect(screen.getByText("org renamed")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
  });

  it("switches to the Request Log tab and renders entries", async () => {
    mockFetchImpl(async (url) => {
      if (url.includes("/api/members")) return jsonResponse([]);
      if (url.includes("/api/settings/request-logs")) {
        return jsonResponse({
          items: [
            {
              id: "r1",
              actor_email: "a@example.com",
              method: "PATCH",
              path: "/api/orgs/current",
              status_code: 200,
              duration_ms: 12,
              created_at: new Date().toISOString(),
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        });
      }
      return jsonResponse({ items: [], total: 0, page: 1, page_size: 50 });
    });
    renderWithProviders(<AuditLogsSettings />);
    await userEvent.click(screen.getByText("Request Log"));
    await screen.findByText("/api/orgs/current");
    expect(screen.getByText("PATCH")).toBeInTheDocument();
  });
});
