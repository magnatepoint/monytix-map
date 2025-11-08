/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Modern AI Fintech Palette - Deep, Professional, Readable
        border: "hsl(220, 20%, 20%)",
        input: "hsl(220, 20%, 18%)",
        ring: "hsl(45, 75%, 55%)",
        background: "hsl(222, 47%, 11%)",
        foreground: "hsl(213, 31%, 91%)",
        primary: {
          DEFAULT: "hsl(45, 75%, 55%)", // Rich gold for primary actions
          foreground: "hsl(222, 47%, 11%)", // Dark text on gold
        },
        secondary: {
          DEFAULT: "hsl(220, 30%, 15%)",
          foreground: "hsl(213, 31%, 91%)",
        },
        destructive: {
          DEFAULT: "hsl(0, 84%, 60%)",
          foreground: "hsl(222, 47%, 11%)",
        },
        muted: {
          DEFAULT: "hsl(220, 25%, 18%)",
          foreground: "hsl(215, 20%, 65%)",
        },
        accent: {
          DEFAULT: "hsl(173, 80%, 40%)",
          foreground: "hsl(222, 47%, 11%)",
        },
        popover: {
          DEFAULT: "hsl(220, 30%, 15%)",
          foreground: "hsl(213, 31%, 91%)",
        },
        card: {
          DEFAULT: "hsl(220, 30%, 13%)",
          foreground: "hsl(213, 31%, 91%)",
        },
        // Enhanced brand accents
        info: "hsl(199, 89%, 48%)",
        success: "hsl(142, 76%, 36%)",
        warning: "hsl(38, 92%, 50%)",
        gold: {
          from: "#F4D03F",
          to: "#D4AF37",
        },
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },
      boxShadow: {
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3)',
        'glow': '0 0 20px rgba(212, 175, 55, 0.4)',
        'glow-accent': '0 0 20px rgba(15, 185, 177, 0.3)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}

