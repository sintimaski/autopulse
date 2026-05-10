import next from "eslint-config-next";

/** @type {import("eslint").Linter.Config[]} */
const eslintConfig = [
  ...next,
  {
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    rules: {
      eqeqeq: ["warn", "always", { null: "ignore" }],
      "no-debugger": "error",
      "import/no-duplicates": "warn",
    },
  },
];

export default eslintConfig;
