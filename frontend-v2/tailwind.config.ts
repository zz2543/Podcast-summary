import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#FBFBFD",
        surface: "#FFFFFF",
        "surface-elev": "#F5F5F7",
        border: "#D2D2D7",
        text: {
          DEFAULT: "#1D1D1F",
          muted: "#6E6E73",
          subtle: "#86868B"
        },
        status: {
          ok: "#34C759",
          warn: "#FF9F0A",
          err: "#FF3B30",
          info: "#0A84FF"
        }
      },
      fontFamily: {
        sans: [
          '"SF Pro Text"',
          '-apple-system',
          'BlinkMacSystemFont',
          'Inter',
          'system-ui',
          'sans-serif'
        ],
        display: [
          '"SF Pro Display"',
          '-apple-system',
          'BlinkMacSystemFont',
          'Inter',
          'system-ui',
          'sans-serif'
        ]
      },
      backdropBlur: {
        glass: "20px"
      },
      boxShadow: {
        glass: "0 1px 0 rgba(255,255,255,0.6) inset, 0 8px 32px rgba(0,0,0,0.06)",
        card: "0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04)",
        "card-hover": "0 2px 4px rgba(0,0,0,0.06), 0 12px 32px rgba(0,0,0,0.08)"
      },
      borderRadius: {
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px"
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" }
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      },
      animation: {
        shimmer: "shimmer 2s linear infinite",
        "fade-in": "fade-in 0.4s ease-out"
      }
    }
  },
  plugins: []
};

export default config;
