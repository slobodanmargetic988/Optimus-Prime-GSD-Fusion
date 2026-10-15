# Contributing to Optimus

Optimus is a free local tool for planning and building software with your own AI
provider. Bug reports, provider compatibility testing, documentation, examples
and focused pull requests are welcome. The repository is public. The CLI is
confirmed usable; the desktop app remains experimental and untested in real
projects. Help test it and send a pull request with any necessary bug fixes.

## Report an issue

Use [GitHub Issues](https://github.com/slobodanmargetic988/Optimus-Prime-GSD-Fusion/issues)
for bugs and suggestions. Include the app version, operating system, provider CLI
version, steps to reproduce and the expected result. Share a minimal example
project when possible. Remove credentials, personal data, private source code and
sensitive paths from logs or screenshots. Report security issues through the
[security process](SECURITY.md).

## Make a change

1. Open an issue for a substantial behavior change so scope can be discussed.
2. Create a branch from the repository's default branch and keep the change focused.
3. Follow [AGENTS.md](AGENTS.md), including the prompt-template change policy.
4. Update relevant documentation and run checks for the behavior you changed.
5. Open a pull request describing the problem, the change and how you verified it.

For desktop work, use Node.js 24 and the commands in [desktop/README.md](desktop/README.md):

```sh
cd desktop
npm ci
npm test
npm run build
```

Runtime work uses Python 3.11+. Run the relevant existing tests and add regression
coverage when changing behavior. Use local fixture executables for provider tests;
do not require real credentials or paid model calls in automated tests. Live
provider results should identify the tested CLI/version and be reported separately.

Never commit API keys, authentication files, local environment files, run logs,
private project inputs or generated installers. Keep upstream attribution and
license files when adding dependencies. Contributions to Optimus are provided
under the [Apache 2.0 license](LICENSE), except where an existing third-party file
has a separate license. Do not add third-party code without its applicable notices.

## Support development

If Optimus is useful to you, [GitHub sponsorship](https://github.com/sponsors/slobodanmargetic988)
is welcome. Sponsorship is optional; helping other users, improving docs and
sharing reproducible bug reports are valuable contributions too.
