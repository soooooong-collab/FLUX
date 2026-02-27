import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        flux: {
          dark: "#1A1A2E",
          deeper: "#16213E",
          accent: "#FF6B35",
          "accent-light": "#FF8F65",
          surface: "#0F3460",
          muted: "#E2E8F0",
        },
      },
    },
  },
  plugins: [],
};
export default config;
