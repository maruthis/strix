import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl } from "../../test/mock-fetch";
import { AddRepositoryModal } from "./AddRepositoryModal";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

describe("AddRepositoryModal", () => {
  it("defaults to the GitHub tab and lists GitHub repos", async () => {
    const fetchMock = mockFetchImpl(async (url) => {
      if (url.includes("provider=github")) return jsonRes([{ full_name: "acme/gh-repo", default_branch: "main", private: false }]);
      return jsonRes([]);
    });
    renderWithProviders(<AddRepositoryModal open onClose={vi.fn()} />);
    await screen.findByText("acme/gh-repo");
    expect(fetchMock).toHaveBeenCalledWith("/api/repositories/installable?provider=github", expect.objectContaining({ method: "GET" }));
  });

  it("switches to the GitLab tab and refetches for gitlab", async () => {
    mockFetchImpl(async (url) => {
      if (url.includes("provider=github")) return jsonRes([{ full_name: "acme/gh-repo", default_branch: "main", private: false }]);
      if (url.includes("provider=gitlab")) return jsonRes([{ full_name: "acme-group/gl-repo", default_branch: "main", private: true }]);
      return jsonRes([]);
    });
    renderWithProviders(<AddRepositoryModal open onClose={vi.fn()} />);
    await screen.findByText("acme/gh-repo");

    await userEvent.click(screen.getByRole("button", { name: "GitLab" }));
    await screen.findByText("acme-group/gl-repo");
    expect(screen.queryByText("acme/gh-repo")).not.toBeInTheDocument();
    expect(screen.getByText("Private")).toBeInTheDocument();
  });

  it("adds a repo with the selected provider in the request body", async () => {
    const fetchMock = mockFetchImpl(async (url, init) => {
      if (url.includes("provider=gitlab")) return jsonRes([{ full_name: "acme-group/gl-repo", default_branch: "main", private: false }]);
      if (init?.method === "POST") return jsonRes({ id: "r1" });
      return jsonRes([]);
    });
    renderWithProviders(<AddRepositoryModal open onClose={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "GitLab" }));
    await screen.findByText("acme-group/gl-repo");

    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST");
      expect(call).toBeTruthy();
      const body = JSON.parse((call![1] as RequestInit).body as string);
      expect(body).toEqual({ full_name: "acme-group/gl-repo", default_branch: "main", provider: "gitlab" });
    });
  });

  it("shows an empty state pointing at Integrations when nothing is left to add", async () => {
    mockFetchImpl(async () => jsonRes([]));
    renderWithProviders(<AddRepositoryModal open onClose={vi.fn()} />);
    await screen.findByText(/No more repositories to add/);
    expect(screen.getByRole("link", { name: "Integrations" })).toHaveAttribute("href", "/integrations");
  });

  it("closes when the Integrations link is clicked", async () => {
    mockFetchImpl(async () => jsonRes([]));
    const onClose = vi.fn();
    renderWithProviders(<AddRepositoryModal open onClose={onClose} />);
    await screen.findByRole("link", { name: "Integrations" });
    await userEvent.click(screen.getByRole("link", { name: "Integrations" }));
    expect(onClose).toHaveBeenCalled();
  });
});
