/** @type {import('tailwindcss').Config} */
import preset from './src/theme/tailwind-preset'

export default {
  presets: [preset],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
