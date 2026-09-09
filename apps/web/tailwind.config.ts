import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        // Neutral chrome is remapped from Tailwind's cool-toned "slate" onto
        // true neutral "zinc" values so every existing `slate-*` class in the
        // app (backgrounds, borders, text) renders as Vercel-style flat gray
        // instead of blue-gray, with no per-file class changes required.
        slate: {
          50: "#fafafa",
          100: "#f4f4f5",
          200: "#e4e4e7",
          300: "#d4d4d8",
          400: "#a1a1aa",
          500: "#71717a",
          600: "#52525b",
          700: "#3f3f46",
          750: "#33333a",
          800: "#27272a",
          850: "#202023",
          900: "#18181b",
          925: "#131316",
          950: "#09090b",
        },
        // The app's "primary/active" accent was indigo; remapped to Vercel's
        // blue so every `indigo-*` class becomes the flat blue accent.
        indigo: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },
        // Cyan was previously paired with indigo for a two-tone gradient
        // identity; aliased to the same blue scale so accents stay single-hue.
        cyan: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },
        surface: {
          50: "#fafafa",
          100: "#f4f4f5",
          700: "#3f3f46",
          750: "#33333a",
          800: "#27272a",
          850: "#1c1c1f",
          900: "#18181b",
          925: "#131316",
          950: "#000000",
        },
        accent: {
          cyan: "#3b82f6",
          emerald: "#10b981",
          amber: "#f59e0b",
          rose: "#ef4444",
          purple: "#a855f7",
          sky: "#3b82f6",
        },
      },
      boxShadow: {
        "inner-light": "inset 0 1px 0 0 rgba(255, 255, 255, 0.06)",
        "inner-glow": "inset 0 0 20px 0 rgba(255, 255, 255, 0.04)",
        "glow-sm": "0 0 15px -3px rgba(59, 130, 246, 0.2)",
        "glow-md": "0 0 25px -5px rgba(59, 130, 246, 0.3)",
        "glow-lg": "0 0 35px -5px rgba(59, 130, 246, 0.35)",
        "glow-cyan": "0 0 25px -5px rgba(59, 130, 246, 0.3)",
        "glow-emerald": "0 0 25px -5px rgba(16, 185, 129, 0.3)",
        xs: "0 1px 2px 0 rgba(0, 0, 0, 0.4)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        glow: "glow 2.5s ease-in-out infinite alternate",
        "fade-in": "fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "slide-up": "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        shimmer: "shimmer 2.5s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        glow: {
          "0%": { boxShadow: "0 0 12px rgba(59, 130, 246, 0.15)" },
          "100%": { boxShadow: "0 0 22px rgba(59, 130, 246, 0.35)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
