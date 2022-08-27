module.exports = {
  content: [
    './ambuda/templates/**/*.html',
    './ambuda/static/js/*.js',
    './ambuda/utils/parse_alignment.py',
    './ambuda/views/proofing.py',
    './ambuda/xml.py',
  ],
  theme: {
    extend: {
      gridTemplateRows: {
        "7": "repeat(7, minmax(0, 1fr))",
      }
    }
  }
}
