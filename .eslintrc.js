module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    'airbnb-base',
  ],
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint'],
  parserOptions: {
    ecmaVersion: 'latest',
  },
  root: true,
  rules: {
    "no-console": ['error', { allow: ['error'] }],
    // Temporarily disabled while we set up JS modules.
    "no-unused-vars": "off"
  },
};
