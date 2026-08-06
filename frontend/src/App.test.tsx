import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("shows the RTR4 learning system heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /RTR4 学习系统/ }),
    ).toBeInTheDocument();
  });

  it("renders independently from previous tests", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /RTR4 学习系统/ }),
    ).toBeInTheDocument();
  });
});
