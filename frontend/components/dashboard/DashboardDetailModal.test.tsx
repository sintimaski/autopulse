/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardDetailModal } from "./DashboardDetailModal";

afterEach(() => {
  cleanup();
});

describe("DashboardDetailModal", () => {
  it("does not render dialog tree when closed", () => {
    render(
      <DashboardDetailModal open={false} title="Evidence" onClose={vi.fn()}>
        <div>body</div>
      </DashboardDetailModal>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders dialog semantics and close control when open", () => {
    render(
      <DashboardDetailModal open title="Evidence" onClose={vi.fn()}>
        <div>body</div>
      </DashboardDetailModal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByRole("heading", { name: "Evidence" }).textContent).toBe("Evidence");
    expect(screen.getByRole("button", { name: "Close" })).toBeInstanceOf(HTMLButtonElement);
  });

  it("invokes onClose when Escape is pressed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <DashboardDetailModal open title="Evidence" onClose={onClose}>
        <p>Modal body</p>
      </DashboardDetailModal>,
    );
    const panel = screen.getByRole("dialog").querySelector('[tabindex="-1"]');
    expect(panel).toBeTruthy();
    (panel as HTMLElement).focus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
