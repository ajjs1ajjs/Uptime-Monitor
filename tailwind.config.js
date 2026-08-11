/** Tailwind build config for the Uptime Monitor frontend.
 *
 * Replaces the runtime Play CDN (cdn.tailwindcss.com) with a static CSS build.
 * Regenerate after changing templates with:
 *   npx -y tailwindcss@3.4.17 -i tailwind-input.css -o internal/api/web/static/tailwind.css --minify --config tailwind.config.js
 */
module.exports = {
  darkMode: 'class',
  content: [
    './internal/api/web/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        accent: { DEFAULT: '#00d9ff', hover: '#00a8cc' },
        'bg-primary': 'var(--bg-primary)',
        'bg-secondary': 'var(--bg-secondary)',
        'bg-card': 'var(--bg-card)',
        'border-dark': 'var(--border-color)',
      },
    },
  },
  plugins: [],
};
