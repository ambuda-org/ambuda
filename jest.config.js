/*
 * For a detailed explanation regarding each configuration property, visit:
 * https://jestjs.io/docs/configuration
 */

module.exports = {
  // Indicates whether the coverage information should be collected while executing the test
  coverageDirectory: "js-coverage-report",
  // Use '@' to refer to the root folder that contains all source modules. 
  moduleNameMapper: {
    "^@/(.*)": "<rootDir>/ambuda/static/js/$1",
  },
  roots: [
  	"<rootDir>/test/js/",
  ],
  testEnvironment: "jsdom",
  // Build all test code with esbuild, for consistency with prod.
  transform: {
    "\\.[jt]s$": [
      "<rootDir>/test/TransformerEsbuild.js",
    ],
  },
};
