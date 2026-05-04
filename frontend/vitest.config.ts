import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["utils/**/*.test.ts", "lib/**/*.test.ts", "components/**/*.test.ts", "components/**/*.test.tsx"],
  },
});
