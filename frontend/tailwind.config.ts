import type { Config } from "tailwindcss";

/**
 * Clinvedica brand tokens, centralized here so every component references
 * `brand-*` / `peach` utility classes instead of hardcoding hex values —
 * one place to update if the brand palette ever changes.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#A32626", // deep maroon red
          dark: "#7A1D1D",
          amber: "#A15E0C",
        },
        peach: {
          50: "#FFF5F2",
        },
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #A32626 0%, #A15E0C 100%)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
