/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./web/*.html", "./web/app.js"],
  theme: {
    extend: {
      colors: {
        "primary": "#137fec",
        "primary-dark": "#0f66bd",
        "primary-hover": "#0e6ad0",
        "background-light": "#f6f7f8",
        "background-dark": "#101922",
        "surface-light": "#ffffff",
        "surface-dark": "#1a2632",
        "card-light": "#ffffff",
        "card-dark": "#1a2632",
        "text-primary": "#1f2937",
        "text-secondary": "#6b7280",
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        arabic: ["IBM Plex Sans Arabic", "sans-serif"],
        sans: ["IBM Plex Sans Arabic", "Cairo", "sans-serif"],
        body: ["IBM Plex Sans Arabic", "Cairo", "sans-serif"],
        num: ["Space Grotesk", "sans-serif"],
        numeric: ["Space Grotesk", "sans-serif"],
        numbers: ["Space Grotesk", "sans-serif"],
      },
      borderRadius: { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", "2xl": "1rem", full: "9999px" },
    },
  },
  plugins: [],
};
