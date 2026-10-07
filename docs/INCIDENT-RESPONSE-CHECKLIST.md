# Your manual checklist — post-incident

Everything here needs **you**, not an agent: accounts you own, a machine you
control, and a conversation with Nakib. Work top to bottom; the order matters.

Background: [SECURITY-INCIDENT-2026-10-07.md](SECURITY-INCIDENT-2026-10-07.md)

### Where this stands — updated 2026-10-07

| Step | State |
|---|---|
| 1 · Tell Nakib | ⏳ **outstanding** — he must pull before running anything |
| 2 · Rotate credentials | ⏳ **in progress** — do it from a different device |
| 3 · Triage this machine | ✅ **done, clean** — see below |
| 4 · Get the fix to Nakib | ⏳ outstanding — the clean code is still uncommitted |
| 5 · Establish provenance | ⏳ outstanding — decides whether other projects on this disk are affected |
| 6 · Decide about git history | ⏳ outstanding — blocks ever making this repo public |
| 7 · Finish S01 | ✅ **done** — the app has been walked end to end, SOS email included |

**Step 3 is complete and came back clean.** The offline Defender scan found
nothing; scheduled tasks, `Run`/`RunOnce` and the startup folders held nothing
unexpected; and a process sweep taken after a reboot and a 10-minute wait showed
no stray detached `node`. Per §3.3 below, that is the "proceed, but watch
account activity" outcome — **it is not a reason to stop rotating credentials.**
The loader had already run many times; a clean host only means it left no
persistence behind, not that it took nothing with it.

---

## Step 1 — Tell Nakib. Now, before anything else. (2 minutes)

His clone has the same infected `babel.config.js`. Every `expo start` or
`npm test` he runs executes it.

Send him this:

> Stop working in the Meridian repo. We found malware in
> `frontend/babel.config.js` that has been there since the first commit — it
> runs on every build. Don't run `npm install`, `expo start`, or any test until
> I've pushed the fix. Read `docs/SECURITY-INCIDENT-2026-10-07.md` when you
> pull. Treat your machine as potentially compromised: rotate anything you've
> signed into, and check for stray `node` processes.

**Why first:** every minute he keeps building is another execution.

---

## Step 2 — Rotate credentials (30–45 minutes)

The payload ran with full Node privileges — filesystem, network, child
processes — and your `.env` files are committed to the repo. Assume everything
below was readable.

Do these in order; the first two matter most.

### 2.1 Supabase

Dashboard → your project → **Settings → API**

- [ ] **Roll the `service_role` key** — this one bypasses Row Level Security
      entirely. Anyone holding it has unrestricted read/write on every table.
- [ ] **Roll the `anon` key**
- [ ] **Settings → Database → reset the database password**
- [ ] **Settings → API → JWT Settings → roll the JWT secret**
- [ ] Afterwards, update `backend/.env` and `frontend/.env` with the new values,
      then `.\scripts\run.ps1 -Rebuild`

> Rolling the JWT secret signs every existing session out. That is the point.

### 2.2 Anthropic

- [ ] console.anthropic.com → **API Keys** → revoke the key in `backend/.env`,
      create a new one
- [ ] Check **Usage** for spend you don't recognise

### 2.3 Email

- [ ] Google Account → **Security → App passwords** → revoke the one in
      `SMTP_PASSWORD`, generate a new one
- [ ] **Security → Your devices** and **Recent security activity** — look for
      sign-ins you don't recognise
- [ ] Confirm 2FA is on

### 2.4 GitHub

- [ ] **Settings → Developer settings → Personal access tokens** → revoke all,
      reissue only what you need
- [ ] **Settings → SSH and GPG keys** → remove any key you don't recognise;
      consider rotating yours
- [ ] **Settings → Sessions** → sign out everywhere
- [ ] **Security log** — review recent events

### 2.5 Crypto — do not skip this

The malware resolved its C2 through an **Ethereum wallet dead-drop**. That
design is strongly associated with campaigns that target developer machines for
wallet theft.

- [ ] If any wallet, keystore, or seed phrase has **ever** been on this machine:
      **move the funds to a new wallet created on a different, clean device.**
      Rotating a key is not enough — if the seed leaked, the new key derived
      from it leaked too.
- [ ] Check browser extension wallets (MetaMask, Phantom) for unknown approvals
- [ ] Revoke token approvals at revoke.cash

### 2.6 Everything else

- [ ] Browser-saved passwords — assume exposed; change the ones that matter
- [ ] Password manager master password
- [ ] Any cloud CLI you've authenticated (`aws`, `gcloud`, `firebase`,
      `vercel`, `expo`)
- [ ] `~/.npmrc` and `~/.config/anthropic/` for stored tokens

---

## Step 3 — Triage this machine (30 minutes)

### 3.1 Look for persistence

Run each in **PowerShell as Administrator** and read the output. You are looking
for anything referencing `node`, `.js`, a base64 blob, or a name you don't
recognise.

```powershell
# Scheduled tasks not shipped by Microsoft
Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\*' } |
  Select-Object TaskName, TaskPath, State | Format-Table -AutoSize

# Autostart registry keys
'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce',
'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce' |
  ForEach-Object { Write-Host "`n$_"; Get-ItemProperty $_ -EA SilentlyContinue }

# Startup folders
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup" -EA SilentlyContinue
Get-ChildItem "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup" -EA SilentlyContinue

# Node processes you did not start -- the payload spawned detached, hidden ones
Get-Process node -EA SilentlyContinue |
  Select-Object Id, StartTime, Path, @{N='Cmd';E={(Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine}} |
  Format-List

# Outbound connections from node
Get-NetTCPConnection -State Established -EA SilentlyContinue |
  Where-Object { (Get-Process -Id $_.OwningProcess -EA SilentlyContinue).ProcessName -eq 'node' } |
  Select-Object RemoteAddress, RemotePort, OwningProcess
```

- [x] Ran all five — **nothing unexpected**, including a repeat sweep after a
      reboot and a 10-minute wait

A `node` process with `-e` in its command line and no terminal is exactly what
the loader spawned. Note its remote address before killing it.

### 3.2 Scan

- [x] **Windows Security → Virus & threat protection → Scan options →
      Microsoft Defender Offline Scan.** Reboots and scans before Windows
      loads, which catches things a running scan cannot. **Completed — clean.**
- [ ] Optional second opinion: Malwarebytes or ESET Online Scanner.

### 3.3 Decide

**This is where you landed: 3.1 and 3.2 were both clean.** So the loader most
likely ran, fetched its payload, and either failed or did something that
rotating credentials cuts off. Proceed — but keep an eye on account activity for
a few weeks, and finish Step 2.

If **anything** looked wrong: back up your source (not binaries, not
`node_modules`), and reinstall Windows. For a machine holding production
credentials and possibly wallet keys, that is the proportionate response.

---

## Step 4 — Get the fix to Nakib (10 minutes)

The clean code is in your working tree, uncommitted. Commit and push it.

```powershell
cd D:\Meridian

# Confirm the repo scans clean before you commit
bash scripts/scan-injection.sh
bash scripts/check.sh
bash scripts/smoke.sh

git add -A
git commit -m "S01: remove malware from babel.config.js, close 22 defects, dockerise stack, SDK 57

SECURITY: frontend/babel.config.js carried ~26KB of obfuscated malware from
commit db6c42f. Blockchain dead-drop C2, eval + detached spawn, executing on
every Metro bundle and Jest run. Removed; see docs/SECURITY-INCIDENT-2026-10-07.md.

Guards added: scripts/scan-injection.sh, supply-chain CI job, pre-commit hook.
Rotate all credentials -- the payload had full Node privileges."

git push origin agent/Arafat
```

Then tell Nakib:

```powershell
cd <his-repo>
git fetch && git checkout agent/Arafat && git pull
Remove-Item -Recurse -Force frontend\node_modules
npm cache clean --force
cd frontend; npm ci
bash ../scripts/scan-injection.sh    # must say: RESULT: clean
```

- [ ] Pushed
- [ ] Nakib has pulled and his scan is clean

---

## Step 5 — Establish provenance (15 minutes)

**This is the question that decides whether Step 3 was enough.** The malware was
in the *initial* commit, so one of two things happened:

**(a) The source you started from was already infected.** Likely if the project
began from a template, a tutorial repo, a ZIP, or anything from an
"Expo/React Native starter" search result. Then your machine was only ever a
victim of that file, and Steps 2–3 cover you.

**(b) The machine that made that first commit was already compromised**, and the
malware injected itself into your project. Then there may be other infected
projects on your disk, and Step 3's scan matters much more.

Answer these:

- [ ] Where did `frontend/` originally come from? Your own `npx create-expo-app`,
      or something you downloaded?
- [ ] Which machine made commit `db6c42f`? (`git show db6c42f --format="%an %ae %cd"`)
- [ ] Do you have **other** JS/React Native projects on this machine? If yes,
      check each one:

```powershell
# Any babel/metro config that is suspiciously large
Get-ChildItem -Path $HOME, D:\ -Recurse -Include babel.config.js,metro.config.js `
  -ErrorAction SilentlyContinue |
  Where-Object { $_.Length -gt 2KB -and $_.FullName -notlike '*node_modules*' } |
  Select-Object FullName, Length
```

Anything over 2 KB in that list needs looking at. A normal one is under 300
bytes.

- [ ] Checked other projects

---

## Step 6 — Decide about git history (5 minutes)

Commit `db6c42f` still contains the payload. It is inert unless checked out and
executed, so there is no urgency — but:

- [ ] **While the repo stays private:** leave it. The blob is useful for
      provenance, and rewriting history forces Nakib to re-clone.
- [ ] **Before the repo ever goes public:** you must rewrite history, or you
      would be distributing working malware. Use
      [`git-filter-repo`](https://github.com/newren/git-filter-repo):
      ```
      git filter-repo --path frontend/babel.config.js --invert-paths
      ```
      then re-add the clean file. Both of you re-clone afterwards.

Also note: your `.env` files are now committed (your call in S01b, reasonable
for a private repo). The same rule applies — **before going public, the repo
needs history rewritten and every secret rotated**, because deleting a file does
not remove it from history.

---

## Step 7 — Finish S01 ✅ done

Backend verified (`test.sh --ai`: 14/14) **and the app walked end to end** on a
real device against live Supabase:

- [x] **4.1 Register** → row in `profiles`; profile picture → `avatar_url` set
- [x] **4.2 Submit a report** with a real photo → row in `crime_reports`, AI ran
- [x] **4.3 Add an emergency contact** with a real email
- [x] **4.4 Trigger SOS** → **email with the video attached was delivered**

**S01 is closed. S02 (the ADRs and migration runner) is next.**

One caveat to re-check *after* Step 2: 4.4 passing today does not mean it
passes after rotation. Rotating the Supabase keys in 2.1 invalidates what is in
`backend/.env` and `frontend/.env`, so update both and restart before
concluding anything is broken.

Note the 401 advice has changed. Token verification no longer depends on a
shared HS256 secret: `app/core/jwks.py` fetches the project's JWKS and verifies
ES256. After rotation the value that matters is `SUPABASE_URL` being correct —
not the JWT secret.

---

## Quick reference

| | |
|---|---|
| Scan for injected code | `bash scripts/scan-injection.sh` |
| All gates | `bash scripts/check.sh` |
| Every sprint's promises | `bash scripts/smoke.sh` |
| Live backend tests | `bash scripts/test.sh --ai` |
| Start everything | `.\scripts\run.ps1` |
| Stop containers | `.\scripts\run.ps1 -Down` |
| Backend logs | `.\scripts\run.ps1 -Logs` |
