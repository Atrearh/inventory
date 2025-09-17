import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import react from "eslint-plugin-react";

export default [
  js.configs.recommended,
  {
    files: ["front/src/**/*.{js,jsx,ts,tsx}"],
    ignores: ["node_modules", "front/dist", ".venv"],

    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
      },
      globals: {
        console: "readonly",
        document: "readonly",
        window: "readonly",
        TextEncoder: "readonly",
        MutationObserver: "readonly",
        self: "readonly",
        fetch: "readonly",
      },
    },

    plugins: {
      "@typescript-eslint": tseslint,
      react,
    },

    rules: {
      "no-unused-vars": "warn",
      "no-console": "off",
      "react/prop-types": "off",
      "react/jsx-uses-react": "off",
      "react/react-in-jsx-scope": "off",
    },

    settings: {
      react: {
        version: "detect",
      },
    },
  },
];
