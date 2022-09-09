/*
 * For a detailed explanation regarding each configuration property, visit:
 * https://jestjs.io/docs/configuration
 */

module.exports = {
  collectCoverageFrom: [
    "ambuda/static/js/*.{js,ts}",
  ],
  // Indicates whether the coverage information should be collected while executing the test
  coverageDirectory: "js-coverage-report",
  coverageThreshold: {
    global: {
      statements: 70,
      branches: 70,
      functions: 70,
      lines: 70,
    }
  },
  // Use '@' to refer to the root folder that contains all source modules.
  moduleNameMapper: {
    "^@/(.*)": "<rootDir>/ambuda/static/js/$1",
  },
  roots: [
    "<rootDir>/test/js/",
  ],
  testEnvironment: "jsdom",
};
