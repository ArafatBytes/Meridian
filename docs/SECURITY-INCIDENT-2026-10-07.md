# Security incident — malware in `frontend/babel.config.js`

**Found:** 2026-10-07, during the first ever ESLint run on this codebase.
**Severity:** Critical — arbitrary remote code execution, triggered by every build.
**Status:** Removed from the working tree. **Credential rotation and host triage are outstanding.**

---

## 1. Summary

`frontend/babel.config.js` contained approximately 26 KB of obfuscated
JavaScript appended after the legitimate config's closing `};`, separated by
~400 spaces so that it sat off the right edge of an editor window. The real
config is 5 lines; the file was 26,409 bytes with a single 26,295-character
line.

It was **present in the initial commit (`db6c42f`)** and was never modified
afterwards, so it has been in the repository for its entire history.

`babel.config.js` is read and executed by Metro on every bundle and by
`babel-jest` on every test run. Any `expo start`, `npm test`, or `npx jest` in
this project executed it.

---

## 2. What it did

Reconstructed by decoding the obfuscated string table as data. **The payload
was never executed deliberately during analysis.**

### Stage 1 — blockchain dead-drop resolver

Rather than embedding a C2 address, it read one off the public Ethereum chain:

1. `eth_blockNumber` to find the chain head, racing five RPC providers.
2. `eth_getBlockByNumber` / `eth_getTransactionCount` to locate the most recent
   transaction sent by a hardcoded wallet address, using a binary search over
   nonces with a fallback to a Blockscout indexer query.
3. The **`to` address of that transaction** was then reinterpreted as bytes and
   decoded into **two IPv4 addresses**.

This is the significant design choice. The C2 address is not in the file, so
static analysis and domain takedowns do not reach it, and the operator can
repoint every infected host by publishing a single transaction.

### Stage 2 — payload retrieval

- `GET`/`POST` to `https://<decoded-ip-1>:443/0x/ls` and
  `https://<decoded-ip-2>:443/0x/cls`
- Payload delivered either in the body or in an `X-Payload-B64` response header
- Base64-decoded, then XOR-decrypted with one of two embedded keys
- `User-Agent` spoofed as Chrome 131 on Windows 10
- gzip / deflate / brotli decompression handled

### Stage 3 — execution, twice

```js
eval(preamble + payload);                       // in-process
spawn('node', ['-e', preamble + payload], {     // and detached
  detached: true,
  stdio: 'ignore',
  windowsHide: true,
}).unref();
```

The second form survives the build process exiting, produces no console output,
and shows no window. It also seeded globals (`_V`, `_H`, `_H2`, `_t_s`, `_t_u`,
`r = require`, `m = module`) giving the second stage full Node privileges —
filesystem, network, child processes.

---

## 3. Indicators of compromise

### Host / network

| Type | Value |
|---|---|
| Dead-drop wallet (Ethereum mainnet) | `0xa322E5f3D311D3080e6f0121063e9aDC2490Ef1a` |
| C2 paths | `:443/0x/ls`, `:443/0x/cls` |
| C2 payload header | `X-Payload-B64` |
| Spoofed User-Agent | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36` |
| XOR keys (payload) | `q4FZkxX{!h,Sr3=@` · `y-p_>d$0B&@^1aQk` |
| XOR key (string table) | `0xC9` |
| Env var read | `ETH_RPC_URL` |

RPC providers used for resolution — **legitimate services being abused, not
malicious in themselves:**
`1rpc.io/eth`, `eth-mainnet.public.blastapi.io`, `eth.drpc.org`,
`ethereum-rpc.publicnode.com`, `eth.blockscout.com/api`

### File

| | |
|---|---|
| Path | `frontend/babel.config.js` |
| SHA-256 (infected) | `7365273efa4e93bd1036ad2357313494b234cecdd3dd1839d3f0e2e66e815aa7` |
| Size (infected) | 26,409 bytes · 7 lines · longest line 26,295 chars |
| Size (clean) | 636 bytes · longest line 77 chars |
| First seen | commit `db6c42f` ("Initial project push") |

Evidence copies are preserved **outside the repository**, in the session
scratchpad under `incident/`:
`babel.config.js.INFECTED`, `babel.config.js.from-HEAD`.

---

## 4. Scope of the audit

209 tracked and untracked files were scanned as text for: oversized config
files, lines over 2,000 characters, hex string-array obfuscation, `eval` /
`new Function` / `child_process` / `spawn`, `require` of `http`/`https`/`zlib`/
`net`/`dns`/`tls`, `TextDecoder` + hex `Buffer.from`, blockchain RPC method
names, `windowsHide`, `detached`, and npm lifecycle hooks.

**One infected file. Four false positives, all verified benign:**

| File | Signal | Verdict |
|---|---|---|
| `backend/app/services/ai/scene_classification_service.py` | `eval(` | `self.model.eval()` — PyTorch inference mode |
| `frontend/src/services/speech.service.ts` | `exec(` | `/\.(\w+)$/.exec(filename)` — a regex |
| `IMPLEMENTATION_PLAN.md` | 583-char line | a Markdown table row |
| `Meridian_Concept_Document.md` | 541-char line | a Markdown paragraph |

`frontend/package.json` declares **no** `preinstall`/`postinstall`/`prepare`
hooks, so there was no install-time execution vector. Every other config and
entry file is of normal size with normal line lengths. `node_modules` was not
scanned: it is not committed and is reproducible from the lockfile — but see
§6, it should be rebuilt from scratch.

---

## 5. Remediation

### Done

- [x] `frontend/babel.config.js` reduced to its legitimate 5 lines
- [x] Evidence preserved outside the repository
- [x] Repository-wide audit (§4)
- [x] `scripts/scan-injection.sh` written — config size limits, long-line
      detection, IoC signatures, dynamic execution in config files, npm
      lifecycle hooks
- [x] Scanner **validated against the preserved sample** — it reports 4
      findings on the infected file and clean on the repaired one. A detector
      never tested against the known-bad is not a detector.
- [x] Wired into `pre-commit`, a dedicated `supply-chain` CI job, and
      `scripts/smoke.sh` (`demo_S01c`)

- [x] **`node_modules` deleted and reinstalled from the lockfile** with the npm
      cache cleared first (the payload had full Node privileges, so a tampered
      cached tarball was conceivable). `npm ci` restored 1,175 packages.
- [x] **Registry signatures verified:** `npm audit signatures` reports
      **1,175/1,175 packages with verified registry signatures** and 178 with
      build attestations. That is cryptographic evidence the installed tree
      matches what the npm registry published, which is the strongest available
      assurance that the dependency tree itself was not the vector.
- [x] **One postinstall script left blocked, deliberately.** npm 11 gated
      `unrs-resolver@1.12.2` (`eslint-config-expo` →
      `eslint-import-resolver-typescript` → `unrs-resolver`). Reviewed: its
      postinstall is four lines of `napi-postinstall` selecting a prebuilt
      native binary, and the repository is legitimate
      (`github.com/unrs/unrs-resolver`). ESLint, tsc and Jest were all verified
      to work with it still blocked, so it stays blocked. Approving an install
      script should require a reason, not a warning you got tired of seeing.

### Outstanding — owner action

- [ ] **Rotate every credential this machine has touched.** The payload ran
      with full Node privileges, and `.env` files are committed to this repo
      (S01b decision 1):
  - Supabase: `service_role` key, `anon` key, database password, JWT secret
  - Anthropic API key
  - SMTP app password
  - GitHub tokens and SSH keys
  - Browser-stored and password-manager credentials
  - **Any crypto wallet keys or seed phrases on this host** — the blockchain
    dead-drop is characteristic of crypto-targeting campaigns
- [ ] **Triage the host.** Offline AV/EDR scan. Look for persistence:
      scheduled tasks, `Run`/`RunOnce` registry keys, startup folder entries,
      and stray detached `node` processes.
- [ ] **Tell Nakib.** His clone contains the same file. He must not run
      `npm install`, `expo start`, or any test until he has pulled the fix.
- [ ] **Delete `node_modules` and reinstall** from the lockfile on every
      machine.
- [ ] **Establish provenance.** The file arrived in the initial commit, so
      either the source it was copied from was already compromised, or the
      machine that made that commit was. Determining which decides whether host
      triage is sufficient.
- [ ] Consider reporting the wallet address to the RPC providers being abused.

### Not done, deliberately

- **Git history was not rewritten.** The infected blob remains reachable in
  commit `db6c42f`. Rewriting history on a two-person repository is feasible,
  but the blob is inert unless checked out and executed, and preserving it is
  useful for provenance. **If this repository is ever made public, rewrite the
  history first** — it would otherwise distribute working malware.

---

## 6. Why it went unnoticed for so long, and what caught it

The payload was invisible to a reader: the file *looks* correct, because the
legitimate config is the only thing on screen. No test, type check, or build
would ever report it — from Metro's perspective the config is valid and the rest
of the file is just more JavaScript to evaluate.

What found it was **running ESLint for the first time**. The config
(`extends: '@react-native'`) referenced a package that had never been installed,
so lint had never once run in this project. On the first successful run, ESLint
reported nine `no-undef` errors in `babel.config.js` for `Buffer`,
`TextDecoder` and `AbortController` — Node APIs that have no business in a Babel
config.

That is the same pattern as defects 20–24 on the Python side and 25–26 on the
JavaScript side: **tooling that had never been executed was concealing real
problems.** The value of a clean install is not that it is tidy; it is that
nothing gets to hide behind "it works on my machine".

Two process changes follow from this:

1. **A linter that cannot run is worse than no linter**, because its presence
   implies coverage that does not exist. CI now fails if any gate cannot
   execute.
2. **Config and entry files get size and content limits.** They are small,
   rarely change, and execute with full privileges on every build — which makes
   a size anomaly in one of them a high-signal, nearly free check.
