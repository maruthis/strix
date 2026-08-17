import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl, mockFetchJson } from "../../test/mock-fetch";
import IssuesList from "./IssuesList";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

function makeIssue(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "i1",
    org_id: "o1",
    pentest_id: null,
    pr_review_id: null,
    repository_id: "r1",
    domain_id: null,
    title: "SQL injection",
    description: "",
    severity: "critical",
    status: "open",
    cvss: null,
    cvss_breakdown: {},
    technical_analysis: "",
    remediation_steps: "",
    poc_description: "",
    poc_script_code: "",
    code_before: null,
    code_after: null,
    target: "acme/widgets",
    endpoint: "",
    fix_effort: "low",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

const RESPONSE = {
  items: [makeIssue()],
  severity_counts: { critical: 1, high: 0, medium: 0, low: 0 },
  status_counts: { all: 1, open: 1, in_progress: 0, snoozed: 0, fixed: 0, ignored: 0 },
};

describe("IssuesList", () => {
  it("shows an empty state when there are no issues", async () => {
    mockFetchJson({ body: { items: [], severity_counts: { critical: 0, high: 0, medium: 0, low: 0 }, status_counts: { all: 0 } } });
    renderWithProviders(<IssuesList />);
    await screen.findByText("No issues");
  });

  it("renders the severity summary, tabs, and issue rows", async () => {
    mockFetchJson({ body: RESPONSE });
    renderWithProviders(<IssuesList />);
    await screen.findByText("SQL injection");
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Open/ })).toBeInTheDocument();
  });

  it("filters issues client-side by search text", async () => {
    mockFetchJson({ body: RESPONSE });
    renderWithProviders(<IssuesList />);
    await screen.findByText("SQL injection");
    await userEvent.type(screen.getByPlaceholderText("Search issues..."), "nonexistent");
    expect(screen.queryByText("SQL injection")).not.toBeInTheDocument();
  });

  it("switches status tabs", async () => {
    mockFetchJson({ body: RESPONSE });
    renderWithProviders(<IssuesList />);
    await screen.findByText("SQL injection");
    await userEvent.click(screen.getByText("Fixed"));
  });

  it("switches to board view and groups issues by status", async () => {
    mockFetchJson({
      body: {
        items: [makeIssue({ id: "i1", status: "open" }), makeIssue({ id: "i2", status: "fixed", title: "XSS" })],
        severity_counts: { critical: 2, high: 0, medium: 0, low: 0 },
        status_counts: { all: 2, open: 1, fixed: 1 },
      },
    });
    renderWithProviders(<IssuesList />);
    await screen.findByText("SQL injection");

    await userEvent.click(screen.getByText("Board"));
    await screen.findByText("XSS");
    // Tabs (button-rendered) are hidden in board mode, though "Fixed" still
    // appears as a Board column label (a <span>, not a <button>).
    expect(screen.queryByRole("button", { name: "Fixed" })).not.toBeInTheDocument();
  });

  it("shows nothing in board mode when there are no issues at all", async () => {
    mockFetchJson({ body: { items: [], severity_counts: { critical: 0, high: 0, medium: 0, low: 0 }, status_counts: { all: 0 } } });
    renderWithProviders(<IssuesList />);
    await screen.findByText("No issues");
    await userEvent.click(screen.getByText("Board"));
  });
});
