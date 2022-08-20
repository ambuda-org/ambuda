module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    'airbnb-base',
  ],
  parserOptions: {
    ecmaVersion: 'latest',
  },
  rules: {
    "no-console": ['error', { allow: ['error'] }],
    // Temporarily disabled while we set up JS modules.
    "no-unused-vars": "off"
  },
};
