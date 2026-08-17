import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl } from "../../test/mock-fetch";
import AuditLogsSettings from "./AuditLogsSettings";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AuditLogsSettings", () => {
  it("shows an empty state when there's no activity", async () => {
    mockFetchImpl(async () => ({ ok: true, status: 200, json: async () => [] }));
    renderWithProviders(<AuditLogsSettings />);
    await screen.findByText("No activity yet");
  });

  it("renders audit log entries", async () => {
    mockFetchImpl(async () => ({
      ok: true,
      status: 200,
      json: async () => [
        { id: "e1", actor_email: "a@example.com", action: "org.renamed", target: "Acme", extra: {}, created_at: new Date().toISOString() },
      ],
    }));
    renderWithProviders(<AuditLogsSettings />);
    await screen.findByText("a@example.com");
    expect(screen.getByText("org renamed")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
  });
});
