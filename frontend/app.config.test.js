/**
 * The Android build must not depend on a file that is gitignored.
 *
 * `google-services.json` is ignored by design, so it exists on whichever
 * machine downloaded it and nowhere else. app.json pointed at it anyway, and
 * `expo prebuild` does not warn about a missing target — it aborts, taking the
 * whole build with it, on every machine but one.
 *
 * These tests pin both halves of the conditional. The last is the one that
 * matters in a year: it fails if somebody "fixes" a future ENOENT by deleting
 * the pointer from app.json, which would turn a loud build failure into push
 * that is silently off even for the person holding the file.
 */
const fs = require('fs');
const path = require('path');

const appJson = require('./app.json');

const TARGET = path.join(__dirname, 'google-services.json');
const realExistsSync = fs.existsSync;

/**
 * A fresh copy of the module, then the stub.
 *
 * Fresh, because it keeps a "said it already" flag and a test that depended on
 * suite order to see the warning would be a flake. The require happens BEFORE
 * the stub is installed: babel and jest's own transform call `fs.existsSync`
 * while resolving a module, so requiring under a blanket stub fails inside
 * `loadPartialConfigSync` rather than in anything being tested. The stub is
 * also narrowed to the one path, for the same reason.
 */
const load = exists => {
  let mod;
  jest.isolateModules(() => {
    mod = require('./app.config.js');
  });
  jest
    .spyOn(fs, 'existsSync')
    .mockImplementation(p => (p === TARGET ? exists : realExistsSync(p)));
  return mod;
};

const resolve = exists => load(exists)({ config: { ...appJson.expo } });

describe('app.config.js', () => {
  let warn;

  beforeEach(() => {
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('drops the FCM pointer when the file is not there, and says so', () => {
    const config = resolve(false);

    expect(config.android.googleServicesFile).toBeUndefined();
    expect(warn).toHaveBeenCalledTimes(1);
    // The warning has to name the consequence, not just the file, or it reads
    // as noise and gets scrolled past.
    expect(warn.mock.calls[0][0]).toMatch(/Remote push/);
  });

  it('keeps the FCM pointer when the file is there, in silence', () => {
    const config = resolve(true);

    expect(config.android.googleServicesFile).toBe('./google-services.json');
    expect(warn).not.toHaveBeenCalled();
  });

  it('says it once per process, not once per config read', () => {
    const withFirebase = load(false);

    // Expo evaluates the config several times per command — three, for a
    // prebuild.
    withFirebase({ config: { ...appJson.expo } });
    withFirebase({ config: { ...appJson.expo } });
    withFirebase({ config: { ...appJson.expo } });

    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('looks for the file next to app.json, not next to the shell', () => {
    // A relative existsSync would resolve against the working directory, so
    // whether the pointer survived would depend on where run.ps1 was invoked
    // from. The narrowed stub only answers for the absolute path, so this test
    // fails outright if the lookup stops being absolute.
    const config = resolve(true);

    expect(config.android.googleServicesFile).toBe('./google-services.json');
    expect(fs.existsSync).toHaveBeenCalledWith(TARGET);
  });

  it('changes nothing else about the build', () => {
    const config = resolve(false);

    // The bundle id can never change after the first Play release, the plugin
    // list is the native surface, and the projectId is how push is addressed.
    expect(config.android.package).toBe(appJson.expo.android.package);
    expect(config.android.permissions).toEqual(
      appJson.expo.android.permissions,
    );
    expect(config.android.config).toEqual(appJson.expo.android.config);
    expect(config.plugins).toEqual(appJson.expo.plugins);
    expect(config.extra).toEqual(appJson.expo.extra);
    expect(config.owner).toBe(appJson.expo.owner);
    expect(config.scheme).toBe(appJson.expo.scheme);
    expect(config.ios).toEqual(appJson.expo.ios);
  });

  it('declares the pointer in app.json, so the conditional has work to do', () => {
    expect(appJson.expo.android.googleServicesFile).toBe(
      './google-services.json',
    );
  });
});
