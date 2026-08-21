import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
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
  target_branch: "main",
  resolved_head_sha: "abc1234",
  error: null,
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

  it("shows a scanning indicator and no finding count while a review is running", async () => {
    mockFetchJson({ body: { items: [{ ...REVIEW, status: "running", findings_count: 0 }], counts: { all: 1 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    expect(screen.getByText(/scanning…/)).toBeInTheDocument();
    expect(screen.queryByText(/finding\(s\)/)).not.toBeInTheDocument();
  });

  it("shows the failure reason for a failed review", async () => {
    mockFetchJson({ body: { items: [{ ...REVIEW, status: "failed", error: "scan_failed" }], counts: { all: 1 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    expect(screen.getByText("scan_failed")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mockFetchJson({ body: { items: [REVIEW], counts: { all: 1 } } });
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    await userEvent.type(screen.getByPlaceholderText("Search repository, title, or PR number"), "x");
  });

  it("debounces search input instead of firing a request per keystroke", async () => {
    const fetchMock = mockFetchImpl(async () => jsonRes({ items: [REVIEW], counts: { all: 1 } }));
    renderWithProviders(<PRReviewsList />);
    await screen.findByText(/Add withdraw endpoint/);
    const callsBeforeTyping = fetchMock.mock.calls.length;

    await userEvent.type(screen.getByPlaceholderText("Search repository, title, or PR number"), "widgets");
    // No new request fires immediately for each keystroke.
    expect(fetchMock.mock.calls.length).toBe(callsBeforeTyping);

    // Once typing settles, exactly one debounced request goes out with the
    // full search term.
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter((call) => String(call[0]).includes("search=widgets")).length).toBe(1);
    });
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
    it("submits a manual review and shows the queued toast", async () => {
      const fetchMock = mockFetchImpl(async (url, init) => {
        if (url.endsWith("/api/repositories")) return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        if (url.endsWith("/pull-requests")) return jsonRes([]);
        if (init?.method === "POST" && url.endsWith("/api/pr-reviews")) return jsonRes({ ...REVIEW, status: "running", findings_count: 0, target_branch: null });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("Select a connected repository, then choose an open pull request or enter its number.");

      await userEvent.click(await screen.findByText("acme/widgets"));
      await screen.findByText("PR number");
      await userEvent.type(screen.getByPlaceholderText("42"), "7");
      await userEvent.type(screen.getByPlaceholderText("Add wallet withdraw endpoint"), "Some PR");
      await userEvent.click(screen.getByRole("button", { name: "Run review" }));

      await waitFor(() => {
        const call = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST");
        expect(call).toBeTruthy();
        const body = JSON.parse((call![1] as RequestInit).body as string);
        // No PR was picked from a live list, so no target_branch is sent —
        // the backend falls back to the repository's default branch.
        expect(body.target_branch).toBeUndefined();
      });
    });

    it("sends the picked PR's target_branch when submitting", async () => {
      const fetchMock = mockFetchImpl(async (url, init) => {
        if (url.endsWith("/api/repositories")) return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        if (url.endsWith("/pull-requests")) {
          return jsonRes([{ number: 42, title: "Add wallet withdraw endpoint", author: "octocat", source_branch: "feature/withdraw", target_branch: "develop", url: null }]);
        }
        if (init?.method === "POST" && url.endsWith("/api/pr-reviews")) return jsonRes({ ...REVIEW, status: "running", findings_count: 0, target_branch: "develop" });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await userEvent.click(await screen.findByText("acme/widgets"));
      await screen.findByText("Add wallet withdraw endpoint");
      await userEvent.click(screen.getByText("Add wallet withdraw endpoint"));

      await screen.findByText("PR number");
      await userEvent.click(screen.getByRole("button", { name: "Run review" }));

      await waitFor(() => {
        const call = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST");
        expect(call).toBeTruthy();
        const body = JSON.parse((call![1] as RequestInit).body as string);
        expect(body.target_branch).toBe("develop");
      });
    });

    it("filters the repository list by search, and lets you change the selection", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) {
          return jsonRes([
            { id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 },
            { id: "r2", provider: "github", full_name: "acme/gadgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 },
          ]);
        }
        if (url.endsWith("/pull-requests")) return jsonRes([]);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("acme/gadgets");

      await userEvent.type(screen.getByPlaceholderText("Search repositories"), "wid");
      expect(screen.getByText("acme/widgets")).toBeInTheDocument();
      expect(screen.queryByText("acme/gadgets")).not.toBeInTheDocument();

      await userEvent.click(screen.getByText("acme/widgets"));
      await screen.findByText("Change");
      await userEvent.click(screen.getByText("Change"));
      await screen.findByPlaceholderText("Search repositories");
    });

    it("shows an empty state when there are no connected repositories to review", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) return jsonRes([]);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("No connected repositories found.");
    });

    it("resets the picker and closes on X from both steps", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) {
          return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        }
        if (url.endsWith("/pull-requests")) return jsonRes([]);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await screen.findByText("acme/widgets");

      // Closing from the repo-picker step.
      const modal = screen.getByText("Review a pull request").closest("div")!.parentElement!;
      await userEvent.click(modal.querySelector("button")!);
      expect(screen.queryByText("Review a pull request")).not.toBeInTheDocument();

      // Reopen and close from the details step.
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await userEvent.click(await screen.findByText("acme/widgets"));
      await screen.findByText("PR number");
      const modal2 = screen.getByText("Review a pull request").closest("div")!.parentElement!;
      await userEvent.click(modal2.querySelector("button")!);
      expect(screen.queryByText("Review a pull request")).not.toBeInTheDocument();
    });

    it("lists open pull requests once a repository with a live integration is selected, and lets you pick one", async () => {
      mockFetchImpl(async (url, init) => {
        if (url.endsWith("/api/repositories")) {
          return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        }
        if (url.endsWith("/pull-requests")) {
          return jsonRes([
            { number: 42, title: "Add wallet withdraw endpoint", author: "octocat", source_branch: "feature/withdraw", target_branch: "main", url: "https://github.com/acme/widgets/pull/42" },
            { number: 7, title: "Fix CORS misconfiguration", author: "hexbot", source_branch: "fix/cors", target_branch: "main", url: "https://github.com/acme/widgets/pull/7" },
          ]);
        }
        if (init?.method === "POST" && url.endsWith("/api/pr-reviews")) return jsonRes({ ...REVIEW, status: "needs_attention", findings_count: 1 });
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await userEvent.click(await screen.findByText("acme/widgets"));

      await screen.findByText("Fix CORS misconfiguration");
      expect(screen.getByText("by octocat")).toBeInTheDocument();

      await userEvent.click(screen.getByText("Fix CORS misconfiguration"));

      // Picking a PR jumps to the (still-editable) manual form, prefilled.
      await screen.findByText("PR number");
      expect(screen.getByPlaceholderText("42")).toHaveValue(7);
      expect(screen.getByPlaceholderText("Add wallet withdraw endpoint")).toHaveValue("Fix CORS misconfiguration");

      await userEvent.click(screen.getByRole("button", { name: "Run review" }));
    });

    it("falls back straight to manual entry when there are no open pull requests", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) {
          return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        }
        if (url.endsWith("/pull-requests")) return jsonRes([]);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await userEvent.click(await screen.findByText("acme/widgets"));

      await screen.findByText("PR number");
      expect(screen.queryByText("Loading open pull requests…")).not.toBeInTheDocument();
    });

    it("lets you switch from the pull-request picker to manual entry and back", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) {
          return jsonRes([{ id: "r1", provider: "github", full_name: "acme/widgets", default_branch: "main", auto_review_enabled: true, last_tested_at: null, open_issues_count: 0 }]);
        }
        if (url.endsWith("/pull-requests")) {
          return jsonRes([{ number: 42, title: "Add wallet withdraw endpoint", author: "octocat", source_branch: "feature/withdraw", target_branch: "main", url: null }]);
        }
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: "Review a Pull Request" }));
      await userEvent.click(await screen.findByText("acme/widgets"));

      await screen.findByText("Add wallet withdraw endpoint");
      await userEvent.click(screen.getByText("Can't find it? Enter the PR number manually"));

      await screen.findByText("PR number");
      expect(screen.getByPlaceholderText("42")).toHaveValue(null);

      await userEvent.click(screen.getByText("← Pick from open pull requests instead"));
      await screen.findByText("Add wallet withdraw endpoint");
    });
  });

  describe("connect repository modal", () => {
    it("opens from the Connect Repository button and adds a repo", async () => {
      mockFetchImpl(async (url) => {
        if (url.endsWith("/api/repositories")) return jsonRes([]);
        if (url.includes("/installable")) return jsonRes([{ full_name: "acme/new-repo", default_branch: "main", private: false }]);
        return jsonRes({ items: [], counts: { all: 0 } });
      });
      renderWithProviders(<PRReviewsList />);
      await userEvent.click(screen.getByRole("button", { name: /Connect Repository/ }));
      await screen.findByText("acme/new-repo");
      await userEvent.click(screen.getByRole("button", { name: "Add" }));
    });
  });
});
