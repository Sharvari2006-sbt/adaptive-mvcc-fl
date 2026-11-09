/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          800: '#141E33',
          900: '#0B132B',
          950: '#070B1A',
        },
        brand: {
          blue: '#1E40AF',
          teal: '#0D9488',
          cyan: '#06B6D4',
        }
      }
    },
  },
  plugins: [],
}
