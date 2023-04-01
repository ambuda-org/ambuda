module.exports = {
  content: [
    './ambuda/static/js/*.js',
    './ambuda/templates/**/*.html',
    './ambuda/utils/parse_alignment.py',
    './ambuda/utils/xml.py',
    './ambuda/views/proofing/main.py',
  ],
  safelist: [
      // Used by Flask-admin internally -- include it explicitly
      "pagination",
  ],
  plugins: [
    require('@tailwindcss/typography')({
      className: 'tw-prose',
    }),
  ]
}
