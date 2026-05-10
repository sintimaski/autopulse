import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SettingsActiveProjectSection } from "./SettingsActiveProjectSection";

describe("SettingsActiveProjectSection", () => {
  it("renders selector when multiple projects exist", () => {
    const html = renderToStaticMarkup(
      <SettingsActiveProjectSection
        organizationsLoadState="ready"
        accessibleProjects={[
          { id: "p1", label: "Org A / API" },
          { id: "p2", label: "Org B / Worker" },
        ]}
        currentProjectLabel="Org A / API"
        sessionProjectId="p1"
        activeProjectBusy={false}
        activeProjectMessage={null}
        onActiveProjectChange={() => {}}
      />,
    );
    expect(html).toContain("Active project");
    expect(html).toContain("Project for dashboard queries");
    expect(html).toContain("Org A / API");
  });

  it("renders loading message when organizations are still loading", () => {
    const html = renderToStaticMarkup(
      <SettingsActiveProjectSection
        organizationsLoadState="loading"
        accessibleProjects={[]}
        currentProjectLabel={null}
        sessionProjectId={null}
        activeProjectBusy={false}
        activeProjectMessage={null}
        onActiveProjectChange={() => {}}
      />,
    );
    expect(html).toContain("Loading projects");
  });
});
