import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          canvas: "#0B0F14",
          sidebar: "#0D1117",
          surface: "#11161D",
          elevated: "#161B22",
          hover: "#1C222B",
          active: "#252B34",
        },
        text: {
          primary: "#F5F4F1",
          secondary: "#B5B8BD",
          muted: "#848B95",
          disabled: "#616874",
        },
        accent: {
          gold: "#D8A955",
          goldHover: "#E6BB73",
          goldMuted: "rgba(216, 169, 85, 0.12)",
          goldBorder: "rgba(216, 169, 85, 0.35)",
        },
        border: {
          default: "rgba(255, 255, 255, 0.075)",
          subtle: "rgba(255, 255, 255, 0.045)",
          strong: "rgba(255, 255, 255, 0.13)",
        },
      },
      fontFamily: {
        serif: [
          '"Cormorant Garamond"',
          "Georgia",
          "Cambria",
          '"Times New Roman"',
          "Times",
          "serif",
        ],
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"SF Mono"',
          "Consolas",
          '"Liberation Mono"',
          "Menlo",
          "Courier",
          "monospace",
        ],
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "14px",
        full: "9999px",
      },
    },
  },
  plugins: [],
};
export default config;
