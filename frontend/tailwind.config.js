/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/features/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'background': '#051424',
        'surface-dim': '#051424',
        'surface-container-lowest': '#010f1f',
        'surface-container-low': '#0d1c2d',
        'surface-container': '#122131',
        'surface-container-high': '#1c2b3c',
        'surface-container-highest': '#273647',
        'surface-variant': '#273647',
        'secondary': '#e9c349',
        'secondary-container': '#af8d11',
        'on-secondary': '#3c2f00',
        'on-surface': '#d4e4fa',
        'on-surface-variant': '#c6c6cc',
        'outline': '#909096',
        'outline-variant': '#45464c',
        'primary': '#c2c6d8',
        'primary-container': '#1a1f2c',
      },
      spacing: {
        'sidebar-width': '260px',
      },
      fontFamily: {
        'carvist': ['TT Carvist', 'serif'],
        'type-light': ['Type Light Sans', 'sans-serif'],
        'sans': ['Geist', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
