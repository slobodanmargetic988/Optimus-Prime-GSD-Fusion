# Third-party notices

Optimus-owned code is licensed under [Apache 2.0](LICENSE); see [NOTICE](NOTICE).
The project license does not replace the separate licenses of the components
below. Preserve these notices when redistributing source or installers.

## Imported source and development documents

- Assets imported from Slobodan Margetic's Agents repository are listed in
  [the original import manifest](docs/plans/LANE_A_IMPORTED_ASSETS_MANIFEST.md).
  Its MIT notice is retained in [licenses/Agents-MIT.txt](licenses/Agents-MIT.txt).
- `skills/playwright` and `skills/linear` originate from the
  [OpenAI skills collection](https://github.com/openai/skills). Their upstream
  Apache 2.0 texts are retained beside the skills as `LICENSE.txt`. The Playwright
  skill's upstream license includes its Microsoft copyright notice. These files
  are separate from the Playwright software package.
- `.claude/skills/gitnexus` contains development documentation generated from
  [GitNexus](https://github.com/abhigyanpatwari/GitNexus). **This directory is
  separately licensed under PolyForm Noncommercial 1.0.0, not Apache 2.0.** Its
  [license](.claude/skills/gitnexus/LICENSE) and
  [required notice](.claude/skills/gitnexus/NOTICE) are retained. GitNexus is an
  optional development tool; this directory and the GitNexus software are not
  included in the Optimus desktop runtime.

## Desktop dependencies

The exact dependency versions are recorded in `desktop/package-lock.json`.
Direct runtime packages at the time of this notice:

| Component | License | Retained notice |
| --- | --- | --- |
| React, React DOM and their Scheduler runtime | MIT | [React](licenses/react.txt), [React DOM](licenses/react-dom.txt) |
| Lucide React icons | ISC | [Lucide](licenses/lucide-react.txt) |
| Electron | MIT, with separately licensed bundled components | Electron's `LICENSE` and `LICENSES.chromium.html` distributed with its runtime |

Build/test dependencies include Vite and electron-builder (MIT), and TypeScript
and Playwright (Apache 2.0). Installed packages retain their own licenses under
`desktop/node_modules`; those files are not committed. Transitive dependencies
retain their respective notices. Release packaging must retain Electron/Chromium
notices and the relevant dependency notices for bundled code.

The Python orchestration runtime uses the standard library. Python, Git, provider
CLIs and project-specific tools are installed separately by users and retain
their own terms. They are not relicensed or bundled as Optimus source.

This inventory records identified components and provenance. When adding or
updating a dependency, review its actual license and update the distributed
notices; the project name or integration with an external tool alone does not
confer rights to that tool.
