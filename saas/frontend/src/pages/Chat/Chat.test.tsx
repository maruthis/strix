import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/render";
import { mockFetchImpl } from "../../test/mock-fetch";
import Chat from "./Chat";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonRes(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

const SUGGESTIONS = {
  categories: ["web", "code"],
  suggestions: {
    web: [{ title: "Test API authorization", prompt: "Check my API endpoints." }],
    code: [{ title: "Review auth code", prompt: "Review authentication." }],
  },
};

describe("Chat", () => {
  it("renders the landing view with category chips and suggestions", async () => {
    mockFetchImpl(async () => jsonRes(SUGGESTIONS));
    renderWithProviders(<Chat />);
    await screen.findByText("What do you want to secure today?");
    await screen.findByText("Test API authorization");

    await userEvent.click(screen.getByText("Code"));
    await screen.findByText("Review auth code");
  });

  it("sends a message via a suggestion card and shows the reply", async () => {
    mockFetchImpl(async (url, init) => {
      if (url.includes("/api/chat/suggestions")) return jsonRes(SUGGESTIONS);
      if (url.includes("/sessions") && !url.includes("/messages") && init?.method === "POST") {
        return jsonRes({ id: "s1", title: "New chat", category: "web", created_at: new Date().toISOString() });
      }
      if (url.includes("/messages")) {
        return jsonRes([
          { id: "m1", role: "user", content: "Check my API endpoints.", created_at: new Date().toISOString() },
          { id: "m2", role: "assistant", content: "Starting a web review.", created_at: new Date().toISOString() },
        ]);
      }
      return jsonRes({});
    });
    renderWithProviders(<Chat />);
    await screen.findByText("Test API authorization");
    await userEvent.click(screen.getByText("Test API authorization"));

    await screen.findByText("Starting a web review.");
    expect(screen.getByText("Check my API endpoints.")).toBeInTheDocument();
  });

  it("submits typed text via Enter, and does not submit on Shift+Enter", async () => {
    mockFetchImpl(async (url, init) => {
      if (url.includes("/api/chat/suggestions")) return jsonRes(SUGGESTIONS);
      if (url.includes("/sessions") && !url.includes("/messages") && init?.method === "POST") {
        return jsonRes({ id: "s1", title: "New chat", category: "web", created_at: new Date().toISOString() });
      }
      if (url.includes("/messages")) {
        return jsonRes([
          { id: "m1", role: "user", content: "hello", created_at: new Date().toISOString() },
          { id: "m2", role: "assistant", content: "hi there", created_at: new Date().toISOString() },
        ]);
      }
      return jsonRes({});
    });
    renderWithProviders(<Chat />);
    await screen.findByText("What do you want to secure today?");

    const textarea = screen.getByPlaceholderText("Tell Strix what to do…");
    await userEvent.type(textarea, "hello{Shift>}{Enter}{/Shift}");
    // Shift+Enter should not have submitted yet.
    expect(screen.queryByText("hi there")).not.toBeInTheDocument();

    await userEvent.type(textarea, "{Enter}");
    await screen.findByText("hi there");
  });

  it("submit button is disabled for blank input", async () => {
    mockFetchImpl(async () => jsonRes(SUGGESTIONS));
    renderWithProviders(<Chat />);
    await screen.findByText("What do you want to secure today?");
    const submitButtons = screen.getAllByRole("button").filter((b) => b.getAttribute("type") === "submit");
    expect(submitButtons[0]).toBeDisabled();
  });

  it("has an inert 'Add repositories' affordance", async () => {
    mockFetchImpl(async () => jsonRes(SUGGESTIONS));
    renderWithProviders(<Chat />);
    await screen.findByText("What do you want to secure today?");
    const button = screen.getByRole("button", { name: /Add repositories/ });
    expect(button).toBeInTheDocument();
    await userEvent.click(button);
  });
});
