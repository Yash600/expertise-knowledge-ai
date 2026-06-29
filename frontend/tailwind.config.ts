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
        bg: "#F5EDE0",
        cream: "#EDE5D8",
        card: "#FFFFFF",
        coral: {
          DEFAULT: "#E8533A",
          light: "#F26B52",
          dark: "#C93E29",
          muted: "#FFF0ED",
        },
        border: "#E8E0D5",
        dark: "#1C1C1C",
        mid: "#555555",
        muted: "#9B9B9B",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "24px",
      },
      boxShadow: {
        card: "0 2px 12px rgba(0,0,0,0.08)",
        "card-hover": "0 4px 20px rgba(0,0,0,0.12)",
        coral: "0 4px 14px rgba(232,83,58,0.3)",
      },
    },
  },
  plugins: [],
};

export default config;
