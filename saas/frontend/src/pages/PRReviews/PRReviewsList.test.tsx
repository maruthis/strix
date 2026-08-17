import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl, mockFetchJson } from "../../test/mock-fetch";
import PRReviewsList from "./PRReviewsList";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

const REVIEW = {
  id: "pr1",
  repository_id: "r1",
  repository_full_name: "acme/widgets",
  pr_number: 42,
  title: "Add withdraw endpoint",
  author: "octocat",
  status: "needs_attention",
  findings_count: 2,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const SETTINGS = {
  rereview_on_push: false,
  target_branches: ["main"],
  approve_clean_prs: false,
  block_prs_on_findings: true,
  blocking_severities: ["critical", "high"],
  exclude_bot_accounts: false,
  excluded_usernames: ["dependabot"],
  allow_overage_reviews: true,
  review_cap_per_dev: null,
  review_cap_period: "month",
};

describe("PRReviewsList", () => {
  it("shows an empty state", async () => {
    mockFetchJson({ body: { items: [], counts: { all: 0 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText("No PR reviews");
  });

  it("renders a review row and switches tabs", async () => {
    mockFetchJson({ body: { items: [REVIEW], counts: { all: 1, needs_attention: 1 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    await userEvent.click(screen.getByText("Needs Attention"));
  });

  it("filters by search text", async () => {
    mockFetchJson({ body: { items: [REVIEW], counts: { all: 1 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    await userEvent.type(screen.getByPlaceholderText("Search repository, title, or PR number"), "x");
  });

  it("switches to board view, hiding tabs", async () => {
    mockFetchJson({ body: { items: [REVIEW], counts: { all: 1 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    await userEvent.click(screen.getByText("Board"));
    expect(screen.queryByRole("button", { name: "Passed" })).not.toBeInTheDocument();
  });

  describe("settings modal", () => {
    it("shows nothing but the modal shell while settings load", async () => {
      mockFetchImpl(async () => new Promise(() => {}));
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: /Settings/ }));
      expect(screen.getByText("PR Review Settings")).toBeInTheDocument();
    });

    it("toggles settings, manages tag lists, blocking severities, and the review cap", async () => {
      let current = { ...SETTINGS };
      mockFetchImpl(async (url, init) => {
        if (url.includes("/api/pr-reviews/settings") && init?.method === "PATCH") {
          const patch = JSON.parse(init.body as string);
          current = { ...current, ...patch };
          return jsonRes(current);
        }
        if (url.includes("/api/pr-reviews/settings")) return jsonRes(current);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: /Settings/ }));
      await screen.findByText("Re-review on push");

      // Toggle a boolean setting.
      const toggles = screen.getAllByRole("button").filter((b) => b.className.includes("rounded-full") && b.className.includes("h-6"));
      await userEvent.click(toggles[0]);

      // Add and remove a target branch.
      await userEvent.type(screen.getByPlaceholderText("branch or pattern…"), "release");
      await userEvent.click(screen.getAllByRole("button", { name: "+ Add" })[0]);
      await screen.findByText("release");
      const releaseChip = screen.getByText("release").closest("span")!;
      await userEvent.click(releaseChip.querySelector("button")!);

      // Toggle a blocking severity chip off then back on.
      await userEvent.click(screen.getByText("critical"));
      await userEvent.click(screen.getByText("critical"));

      // Add an excluded username.
      await userEvent.type(screen.getByPlaceholderText("username…"), "renovate");
      await userEvent.click(screen.getAllByRole("button", { name: "+ Add" })[1]);

      // Set a review cap.
      const capInput = screen.getByPlaceholderText("No cap");
      await userEvent.type(capInput, "5");
      await userEvent.tab();
    });

    it("hides the blocking-severity chips once block_prs_on_findings is off", async () => {
      mockFetchImpl(async (url) => {
        if (url.includes("/api/pr-reviews/settings")) return jsonRes({ ...SETTINGS, block_prs_on_findings: false });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: /Settings/ }));
      await screen.findByText("Re-review on push");
      expect(screen.queryByText("critical")).not.toBeInTheDocument();
    });

    it("clearing the review cap input sends null", async () => {
      mockFetchImpl(async (url, init) => {
        if (url.includes("/api/pr-reviews/settings") && init?.method === "PATCH") return jsonRes({ ...SETTINGS, review_cap_per_dev: null });
        if (url.includes("/api/pr-reviews/settings")) return jsonRes({ ...SETTINGS, review_cap_per_dev: 5 });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: /Settings/ }));
      const capInput = await screen.findByDisplayValue("5");
      await userEvent.clear(capInput);
      await userEvent.tab();
    });
  });

  describe("trigger review modal", () => {
    it("submits a manual review and shows the findings toast", async () => {
      mockFetchImpl(async (url, init) => {
        if (url.endsWith("/api/repositories")) return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        if (init?.method === "POST" && url.endsWith("/api/pr-reviews")) return jsonRes({ ...REVIEW, status: "needs_attention", findings_count: 3 });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("Repository");

      await userEvent.selectOptions(screen.getByDisplayValue("Select a repository…"), "acme/widgets");
      await userEvent.type(screen.getByPlaceholderText("42"), "7");
      await userEvent.type(screen.getByPlaceholderText("Add wallet withdraw endpoint"), "Some PR");
      await userEvent.click(screen.getByRole("button", { name: "Run review" }));
    });

    it("shows the passed toast branch when a review has no findings", async () => {
      mockFetchImpl(async (url, init) => {
        if (url.endsWith("/api/repositories")) return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        if (init?.method === "POST" && url.endsWith("/api/pr-reviews")) return jsonRes({ ...REVIEW, status: "passed", findings_count: 0 });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("Repository");

      await userEvent.selectOptions(screen.getByDisplayValue("Select a repository…"), "acme/widgets");
      await userEvent.type(screen.getByPlaceholderText("42"), "8");
      await userEvent.type(screen.getByPlaceholderText("Add wallet withdraw endpoint"), "Another PR");

      const submit = screen.getByRole("button", { name: "Run review" });
      expect(submit).not.toBeDisabled();
      await userEvent.click(submit);
    });

    it("disables submit until a repository is selected", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) return jsonRes([]);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("Repository");
      expect(screen.getByRole("button", { name: "Run review" })).toBeDisabled();
    });
  });
});
