const { loadBinding } = require('@node-rs/helper')

/**
 * __dirname means load native addon from current dir
 * 'langsmith-nodejs' is the name of native addon
 * the second arguments was decided by `napi.name` field in `package.json`
 * the third arguments was decided by `name` field in `package.json`
 * `loadBinding` helper will load `langsmith-nodejs.[PLATFORM].node` from `__dirname` first
 * If failed to load addon, it will fallback to load from `langsmith-nodejs-[PLATFORM]`
 */
module.exports = loadBinding(__dirname, "langsmith-nodejs", "langsmith-nodejs");
