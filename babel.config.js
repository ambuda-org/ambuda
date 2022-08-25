// FIXME(???): switch to esbuild for consistency with prod
module.exports = {
  presets: [
      ['@babel/preset-env', {targets: {node: 'current'}}],
      "@babel/preset-typescript",
  ],
};
