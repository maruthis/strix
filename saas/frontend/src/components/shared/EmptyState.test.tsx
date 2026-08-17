import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title only", () => {
    render(<EmptyState title="No items" />);
    expect(screen.getByText("No items")).toBeInTheDocument();
  });

  it("renders icon, description, and action when given", () => {
    render(
      <EmptyState
        icon={<span data-testid="icon" />}
        title="No items"
        description="Add one to get started"
        action={<button>Add</button>}
      />
    );
    expect(screen.getByTestId("icon")).toBeInTheDocument();
    expect(screen.getByText("Add one to get started")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });
});
