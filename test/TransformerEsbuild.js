// Compiles JavaScript with esbuild.
//
// We use this because esbuild-jest hasn't been updated in two years.
//
// Aadpted from:
// - https://github.com/aelbore/esbuild-jest/issues/69
// - https://github.com/hannoeru/jest-esbuild/blob/main/src/index.ts

const { createHash } = require("crypto");
const { transformSync } = require("esbuild");
const fs = require("fs");
const { relative } = require("path");

const THIS_FILE = fs.readFileSync(__filename);

const defaultOptions = {
  format: "cjs",
  sourcemap: "both",
  target: `node${process.versions.node}`,
  loader: "ts",
};

module.exports = {
  createTransformer(userOptions) {
    const options = {
      ...defaultOptions,
      ...userOptions,
    };

    return {
      canInstrument: true,

      getCacheKey(fileData, filePath, transformOptions) {
        const { config, instrument, configString } = transformOptions
  
        return createHash('md5')
          .update(THIS_FILE)
          .update('\0', 'utf8')
          .update(JSON.stringify(options))
          .update('\0', 'utf8')
          .update(fileData)
          .update('\0', 'utf8')
          .update(relative(config.rootDir, filePath))
          .update('\0', 'utf8')
          .update(configString)
          .update('\0', 'utf8')
          .update(filePath)
          .update('\0', 'utf8')
          .update(instrument ? 'instrument' : '')
          .update('\0', 'utf8')
          .update(process.env.NODE_ENV || '')
          .digest('hex')
      },

      process(sourceText, sourcePath) {
        const { code, map } = transformSync(sourceText, options);
        return { code, map };
      },
    };
  },
};
