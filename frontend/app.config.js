/**
 * Dynamic app config. Every value still lives in `app.json`; this file changes
 * exactly one of them.
 *
 * `android.googleServicesFile` points at `./google-services.json`, which is
 * gitignored (`.gitignore`, "# Firebase"). The file therefore never travels
 * with a clone, a branch or a merge — only the pointer to it does. A pointer to
 * a file that is not there does not degrade the build, it kills it:
 *
 *     Error: ENOENT: no such file or directory, open
 *     'D:\Meridian\frontend\google-services.json'
 *     [android.dangerous]: withAndroidDangerousBaseMod: Cannot copy
 *     google-services.json ... × Prebuild failed
 *
 * `docs/walkthroughs/B6a.md` step 4 predicted this in writing — it told the
 * reader to add the pointer only *after* downloading the file, because a
 * pointer "to a file that does not exist makes the Android build fail outright,
 * which would have broken a working app for everyone who pulled this branch
 * before doing this step." The pointer was committed anyway, in JG2, and that
 * is precisely what happened on the second machine.
 *
 * So the pointer is now conditional: present when the file is, dropped when it
 * is not. Consequences of dropping it, stated plainly because they are the
 * reason this is a warning and not a silent fix:
 *
 *   - Remote push does not work. `getExpoPushTokenAsync` needs FCM on Android
 *     and throws without it; `notification.service.ts` catches that and returns
 *     null, so nothing crashes — the handset simply never registers a token and
 *     the server has nowhere to send to.
 *   - Journey Guardian's "told if you did not arrive" is server-initiated, so it
 *     is the feature this costs.
 *   - Guardian zone alerts are unaffected. They are LOCAL notifications posted
 *     by the OS on the phone, and need no Firebase project at all.
 *
 * Getting push back needs Nakib's exact `google-services.json`, not a new one:
 * `app.json`'s `owner` is his Expo account, the FCM V1 service-account key
 * uploaded there is from his Firebase project, and a file from a different
 * project carries a different sender ID — which Expo rejects per-send as
 * `MismatchSenderId` (B6a.md names this failure at step 2). Drop his file in at
 * `frontend/google-services.json` and this config picks it up with no edit.
 */
const fs = require('fs');
const path = require('path');

// Expo evaluates the config several times per command, so an unguarded warning
// prints three times in one prebuild. `notification.service.ts` already learned
// this the hard way with `warnedNoProjectId`: repetition makes a correct state
// look like a fault.
let warned = false;

module.exports = ({ config }) => {
  const android = { ...(config.android ?? {}) };

  // EAS Build uploads the git repository, and google-services.json is
  // gitignored, so it never arrives that way -- the cloud build would drop the
  // pointer below and ship without FCM, exactly the "works on my machine"
  // failure this file exists to prevent. A file-type EAS secret named
  // GOOGLE_SERVICES_JSON is materialised into the build workspace and its
  // absolute path exported as this variable, so it takes precedence when set.
  const declared = process.env.GOOGLE_SERVICES_JSON ?? android.googleServicesFile;

  if (declared && fs.existsSync(path.resolve(__dirname, declared))) {
    android.googleServicesFile = declared;
  } else if (declared) {
    delete android.googleServicesFile;
    // Said once per process, and never suppressed entirely: a build that
    // quietly ships without FCM is how push "works on my machine, not yours".
    if (!warned) {
      warned = true;
      console.warn(
        `\n  [meridian] ${declared} is missing, so this build has no FCM.\n` +
          '  Remote push (incl. Journey Guardian overdue alerts) will not reach\n' +
          '  this handset. Local Guardian zone alerts are unaffected.\n' +
          '  Fix: get google-services.json from the Firebase project behind the\n' +
          `  Expo account "${config.owner ?? 'owner'}" and put it in frontend/.\n`,
      );
    }
  }

  return { ...config, android };
};
