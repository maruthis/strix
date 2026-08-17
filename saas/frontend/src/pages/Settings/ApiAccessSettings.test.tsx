import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl } from "../../test/mock-fetch";
import ApiAccessSettings from "./ApiAccessSettings";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

const TOKEN = { id: "t1", name: "CI token", token_type: "personal", scopes: ["read"], token_prefix: "strix_abc12345", status: "active", last_used_at: null, created_at: new Date().toISOString() };
const WEBHOOK = { id: "w1", url: "https://example.com/hook", events: ["pentest.completed"], secret: "shh", status: "active", created_at: new Date().toISOString() };

describe("ApiAccessSettings", () => {
  it("shows the tokens tab by default with an empty state", async () => {
    mockFetchImpl(async () => jsonRes([]));
    renderWithProviders(<ApiAccessSettings />);
    await screen.findByText("No tokens found");
  });

  it("lists tokens and revokes one", async () => {
    mockFetchImpl(async (url, init) => {
      if (init?.method === "DELETE") return jsonRes({ ok: true });
      if (url.includes("/tokens")) return jsonRes([TOKEN]);
      return jsonRes([]);
    });
    renderWithProviders(<ApiAccessSettings />);
    await screen.findByText("CI token");
    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));
  });

  it("creates a new token and shows it once", async () => {
    mockFetchImpl(async (url, init) => {
      if (init?.method === "POST" && url.includes("/tokens")) return jsonRes({ ...TOKEN, token: "strix_abc123456789" });
      if (url.includes("/tokens")) return jsonRes([]);
      return jsonRes([]);
    });
    renderWithProviders(<ApiAccessSettings />);
    await screen.findByText("No tokens found");

    await userEvent.click(screen.getByRole("button", { name: /New Token/ }));
    await userEvent.type(screen.getByPlaceholderText("CI token"), "My token");
    await userEvent.click(screen.getByRole("button", { name: "Create Token" }));

    await screen.findByText("strix_abc123456789");
  });

  it("switches to the webhooks tab, lists webhooks, creates and deletes one", async () => {
    mockFetchImpl(async (url, init) => {
      if (url.includes("/tokens")) return jsonRes([]);
      if (init?.method === "DELETE") return jsonRes({ ok: true });
      if (init?.method === "POST" && url.includes("/webhooks")) return jsonRes({ ...WEBHOOK, id: "w2" });
      if (url.includes("/webhooks")) return jsonRes([WEBHOOK]);
      return jsonRes([]);
    });
    renderWithProviders(<ApiAccessSettings />);
    await screen.findByText("No tokens found");

    await userEvent.click(screen.getByText("webhooks"));
    await screen.findByText("https://example.com/hook");
    expect(screen.getByText("pentest.completed")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /New Webhook/ }));
    await userEvent.type(screen.getByPlaceholderText("https://example.com/webhooks/strix"), "https://other.example.com/hook");
    await userEvent.click(screen.getByRole("button", { name: "Create Webhook" }));

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  });

  it("shows the webhooks empty state", async () => {
    mockFetchImpl(async () => jsonRes([]));
    renderWithProviders(<ApiAccessSettings />);
    await screen.findByText("No tokens found");
    await userEvent.click(screen.getByText("webhooks"));
    await screen.findByText("No webhooks configured");
  });
});
