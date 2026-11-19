import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DeadlineBadge, EligibilityBadge, MatchBadge, SkillChips } from "./Badges";

describe("badges", () => {
  it("labels eligibility states in plain words", () => {
    render(
      <>
        <EligibilityBadge value="eligible" />
        <EligibilityBadge value="not_eligible" />
        <EligibilityBadge value="unknown" />
      </>,
    );
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    expect(screen.getByText("Check manually")).toBeInTheDocument();
  });

  it("shows the closing-soon badge only when needed", () => {
    const { rerender, container } = render(<DeadlineBadge closesSoon={false} closed={false} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<DeadlineBadge closesSoon closed={false} />);
    expect(screen.getByText("Closes in < 24h")).toBeInTheDocument();
    rerender(<DeadlineBadge closesSoon={false} closed />);
    expect(screen.getByText("Closed")).toBeInTheDocument();
  });

  it("shows match score or n/a", () => {
    render(
      <>
        <MatchBadge score={0.75} />
        <MatchBadge score={null} />
        <MatchBadge score={0.1} />
      </>,
    );
    expect(screen.getByText("75% match")).toBeInTheDocument();
    expect(screen.getByText("n/a match")).toHaveAttribute("title", "Notice lists no skills");
    expect(screen.getByText("10% match")).toBeInTheDocument();
  });

  it("renders skill chips", () => {
    render(<SkillChips skills={["Java", "SQL"]} kind="missing" />);
    expect(screen.getByRole("list", { name: "missing skills" })).toHaveTextContent("JavaSQL");
  });

  it("renders None for an empty list", () => {
    render(<SkillChips skills={[]} kind="matched" />);
    expect(screen.getByText("None")).toBeInTheDocument();
  });
});
