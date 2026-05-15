/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#4F46E5',
          dark: '#3730A3',
        },
      },
      fontFamily: {
        display: ['monospace'],
      },
    },
  },
  plugins: [],
}
