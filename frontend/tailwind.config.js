/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ready: "#16a34a",
        blocked: "#dc2626",
        inprogress: "#2563eb",
        done: "#6b7280",
      },
    },
  },
  plugins: [],
}
