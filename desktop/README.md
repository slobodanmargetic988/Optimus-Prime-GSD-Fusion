# Optimus Desktop

Optimus Desktop runs the Optimus planning and build engine on your computer.
It supports new projects, existing Git repositories, saved-run resume, provider
settings, task limits, worker limits and live engine progress. AI usage is billed
by the provider you select.

Optimus is free and open source under [Apache 2.0](../LICENSE), with
[separate notices for third-party components](../THIRD_PARTY_NOTICES.md).
The repository remains private while testing is completed. See [the product contract](../docs/DESKTOP_PRODUCT.md)
and [runtime contract](../docs/contracts/DESKTOP_RUNTIME_CONTRACT.md).

## Requirements

- macOS or Linux: Python **3.11+**, Git, and the selected provider CLI in your
  executable path. The core Python runtime needs no third-party packages.
- Windows: WSL **2** with Python **3.11+**, Git and the provider CLI installed
  **inside the selected Linux distribution**. Windows runs the interface; WSL
  runs the engine. Native Windows engine execution is not supported.
- Codex and OpenRouter require the Codex CLI; Claude requires Claude Code;
  Blackbox requires its CLI. A discovered executable does not verify login,
  account quota or model access.
- Optimus respects the effective Git identity from the repository or user
  configuration. If a name or email is missing, it sets that missing value only
  in the selected repository to `Optimus Desktop` or `optimus@localhost` and logs
  the action. Global Git configuration is unchanged. Set your preferred identity
  in the execution environment if you want commits attributed to you.
- The tools your project needs, such as Node.js, language runtimes, package
  managers or databases, must also be installed in the execution environment.
- API-key storage requires an unlocked OS credential store. On Linux, configure
  a supported secret service; Optimus refuses a plaintext storage fallback.

Provider installation and login instructions: [Codex CLI](https://developers.openai.com/codex/cli),
[Claude Code](https://code.claude.com/docs/en/setup),
[OpenRouter](https://openrouter.ai/docs), and [Blackbox](https://docs.blackbox.ai/).
For Windows setup, see [Microsoft's WSL guide](https://learn.microsoft.com/windows/wsl/install).

## Run from source

Use Node.js 24 and npm. From this repository:

```sh
cd desktop
npm ci
npm start
```

`npm start` builds the interface and opens the real Electron app. The Python
engine is loaded from this checkout. `npm run dev` only starts the browser UI
preview; real project execution requires Electron.

Run `npm test` on macOS/Linux for the backend's local subprocess tests. The
current fixture suite assumes a POSIX execution environment; Windows CI builds
the app and checks staged startup without running those process fixtures.

For interface development, run `npm run dev` in one terminal, then
`npm run desktop:dev` in a second terminal. The launcher works on macOS, Linux
and Windows without shell-specific environment commands.

## First run

1. Open **Preferences** and confirm Python, Git and your provider CLI are detected.
   Set the Python executable path if necessary. On Windows, choose the WSL
   distribution containing those tools.
2. Open **AI providers** and select a provider and authentication mode. Subscription mode uses the
   provider CLI's existing local login. API mode uses your own saved key.
   OpenRouter also needs an explicit model ID. Blackbox planning requires API
   mode; its legacy free lane is not supported for high-effort planning.
3. Choose an empty folder for a new project, or a Git repository for an existing
   project. Existing Optimus state requires **Resume** unless you explicitly
   choose to replace the plan.
4. Describe the result, optionally attach requirements, and set the task,
   worker and cycle limits. Task limit is a maximum plan size; worker count is
   concurrency. These controls are not a fixed model-cost budget.
5. Confirm the project is trusted before starting. Agents can edit files and
   execute local commands. Inspect progress and saved project artifacts.

To inspect the plan before execution, choose **Create the plan first**. After
planning completes, **Build this plan** opens the saved plan for execution
without planning it again. Confirm project permission and start the build.
Optimus verifies the saved plan identity and task limit before continuing; a
changed or invalid plan must be reviewed again.

The app clears inherited API credentials when launching a subscription run to
avoid accidentally selecting API billing. API mode sends only the selected
credential through the child environment. Closing during a build offers to stop
the engine and workers; saved artifacts remain available for resume.

Optional strategy generation uses the selected provider. Enable it in advanced
settings and supply a strategy manifest. It is skipped by default.

On Windows, keep the project in the selected WSL distribution (for example, a
folder opened through `\\wsl.localhost\Ubuntu\home\yourname\projects`) or an
accessible Windows drive. CLI login must happen in that same distribution.
The Python executable setting is a Linux executable/path, not `python.exe`.

## Build installers

Build on the destination operating system. The app includes its engine scripts,
prompt files, skills and schema catalog, but does **not** bundle Python, Git,
provider CLIs, provider credentials or project dependencies.

```sh
npm run build
npm run stage
python3 scripts/check-runtime.py
npm run package
```

On Windows use `python scripts/check-runtime.py`. Generated installers are under
`desktop/release/`: DMG/ZIP for macOS, NSIS EXE for Windows, AppImage/DEB for Linux.
`npm run package:dir` creates an unpacked app for local inspection.
The default architecture is the build machine's architecture. Explicit examples
after building and staging:

```sh
npx electron-builder --mac --arm64 --publish never
npx electron-builder --mac --x64 --publish never
npx electron-builder --win --x64 --publish never
npx electron-builder --linux --x64 --publish never
```

The [desktop build workflow](../.github/workflows/desktop-build.yml) runs on pull
requests affecting the desktop/runtime, manual dispatch, or `desktop-v*` tags.
It builds macOS ARM64/x64, Linux x64 and Windows x64 review installers and uploads
them as temporary workflow artifacts. It has read-only repository permissions,
does not publish releases, and does not use signing credentials. The existing
Lane C release workflow remains independent.

CI verifies frontend compilation and clean staged Python startup on all three
operating systems. Provider/process fixtures run on macOS/Linux. The Windows
package job does not prove WSL execution, and cross-building an Intel Mac package
does not prove Intel runtime behavior. Test installation, provider login,
planning, build, stop and resume on real target environments before release.

## Release status

The app and its updates are free. The **About** page links to the
[GitHub repository](https://github.com/slobodanmargetic988/Optimus-Prime-GSD-Fusion)
and [GitHub Sponsors](https://github.com/sponsors/slobodanmargetic988). Sponsorship
is optional; contributions, bug reports and documentation improvements are welcome.
AI provider usage remains separate and is charged by the provider you choose.

The repository stays private during testing. Before publishing installers,
configure platform signing/notarization, define supported OS/provider versions,
and complete live provider and target-device release checks. Current workflow
artifacts are unsigned review builds. A successful package build does not prove
a signed production release. See the official
[Electron signing guidance](https://www.electronjs.org/docs/latest/tutorial/tutorial-packaging)
and [electron-builder signing configuration](https://www.electron.build/v26/docs/features/code-signing/code-signing-mac/).

## Release QA checklist

Completed locally:

- [x] Native desktop interface, local engine bridge, provider routing and
  saved-plan build flow implemented.
- [x] Provider and process fixtures exercise routing, planning limits, credential
  handling and stop behavior without paid model calls.
- [x] Staged engine starts with a fresh home and Python site packages disabled;
  the required schema document is included.
- [x] Installer matrix configured for macOS ARM64/x64, Linux x64 and Windows x64,
  with read-only artifact uploads and no automatic publication.
- [x] Dependency audit recorded on 2026-10-11: zero production vulnerabilities;
  eight moderate development dependency findings in the `electron-builder`
  dependency chain through `sprintf-js`. These are build-tool findings, not
  production dependency findings. Recheck the lockfile before release and
  address updates or document the release assessment.

Pending before a production release:

- [x] Restore the project’s Apache 2.0 license, retain third-party notices and add
  optional GitHub sponsorship.
- [ ] Review the final publication snapshot, dependency notices and supported versions;
  keep the repository private until the maintainer approves publication.
- [ ] Configure macOS signing/notarization, Windows signing and a signed update
  distribution process; test installation and updates.
- [ ] Run the GitHub installer matrix and test the resulting packages on actual
  target systems, including Intel Mac and Windows with WSL 2.
- [ ] Complete real-provider login, API/subscription selection, planning, build,
  stop and resume checks. Fixture success does not verify live account access
  or provider compatibility.
