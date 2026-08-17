import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/render";
import { mockFetchJson } from "../test/mock-fetch";
import { TrialBanner } from "./TrialBanner";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TrialBanner", () => {
  it("renders nothing while loading", () => {
    mockFetchJson({ body: { plan: "pro_trial", status: "trialing", trial_ends_at: null, card_added: false, current_period_end: null } });
    const { container } = renderWithProviders(<TrialBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows days remaining when trialing without a card", async () => {
    const trialEnds = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString();
    mockFetchJson({ body: { plan: "pro_trial", status: "trialing", trial_ends_at: trialEnds, card_added: false, current_period_end: null } });
    renderWithProviders(<TrialBanner />);
    await screen.findByText(/Add a card/);
    expect(screen.getByText("3 days")).toBeInTheDocument();
  });

  it("renders nothing once a card has been added", async () => {
    mockFetchJson({ body: { plan: "pro_trial", status: "trialing", trial_ends_at: null, card_added: true, current_period_end: null } });
    const { container } = renderWithProviders(<TrialBanner />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("shows a dash for days remaining when trial_ends_at is unset", async () => {
    mockFetchJson({ body: { plan: "pro_trial", status: "trialing", trial_ends_at: null, card_added: false, current_period_end: null } });
    renderWithProviders(<TrialBanner />);
    await screen.findByText(/Add a card/);
    expect(screen.getByText((_, el) => el?.textContent === "— days")).toBeInTheDocument();
  });

  it("renders nothing once status is active", async () => {
    mockFetchJson({ body: { plan: "pro", status: "active", trial_ends_at: null, card_added: true, current_period_end: null } });
    const { container } = renderWithProviders(<TrialBanner />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("adding a card refetches and hides the banner", async () => {
    const trialEnds = new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString();
    mockFetchJson([
      { body: { plan: "pro_trial", status: "trialing", trial_ends_at: trialEnds, card_added: false, current_period_end: null } },
      { body: { ok: true } },
      { body: { plan: "pro_trial", status: "active", trial_ends_at: trialEnds, card_added: true, current_period_end: null } },
    ]);
    renderWithProviders(<TrialBanner />);
    const addCardButton = await screen.findByText("Add card");
    await userEvent.click(addCardButton);
    await waitFor(() => expect(screen.queryByText("Add card")).not.toBeInTheDocument());
  });
});
