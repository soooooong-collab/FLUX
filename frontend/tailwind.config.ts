import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        flux: {
          blue: "#376DF4", // Primary button blue
          "blue-hover": "#2B5AE8",
          "muted-blue": "#EBF1FF",
          dark: "#0F172A", // Slate 900 for dark text
          surface: "#FFFFFF", // White cards
          muted: "#64748B", // Slate 500 for secondary text
          border: "#E2E8F0", // Slate 200 for borders
          background: "#F8FAFC", // Slate 50 for main background
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'), // optional if needed later
    require('@tailwindcss/forms'),      // optional but good for inputs
  ],
};
export default config;
