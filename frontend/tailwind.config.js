/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./src/operations/**/*.{js,ts,jsx,tsx}",
    "./src/operations/components/agent-settings/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#c026d3",
          soft: "#fff0ff",
          pink: "#ff77ff",
        },
      },
    },
  },
  plugins: [],
};
