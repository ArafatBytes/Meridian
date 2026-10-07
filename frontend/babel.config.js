// Cleaned 2026-10-07. See PROGRESS.md "SECURITY INCIDENT".
//
// This file previously contained ~26 KB of obfuscated malware appended after
// the closing brace, padded with ~400 spaces so it sat off-screen. It was
// present from the initial commit (db6c42f). babel.config.js is executed on
// every Metro bundle and every Jest run, which made it an effective
// persistence point.
//
// Keep this file tiny and boring. `scripts/smoke.sh` and the pre-commit hook
// now fail if it grows past a sane size or gains a long line.
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
  };
};
