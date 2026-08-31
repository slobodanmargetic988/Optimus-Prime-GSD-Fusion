# OP Beginner Demo

This guide is for someone who is not a programmer and wants to try OP on a
small new app.

## What OP does

OP helps turn a short idea into a small working project. First it plans the
work: it reads your mission and scope, decides what needs to be done, and writes
a plan. Then it builds: it asks Codex workers to create the files, check the
result, and leave notes about what happened.

## Prepare the folder

Create a new empty folder for the demo. Inside that folder, create two text
files:

- `mission.md`
- `scope.md`

`mission.md` should describe what you want in one or two short paragraphs.

Example:

```markdown
# Mission

Make a tiny web app called Mini Notes.

The app should let me write a short note, save it in the browser, see my saved
notes, and delete notes I no longer need.
```

`scope.md` should describe what belongs in the first demo version. Keep it
small. For the first demo, do not ask for accounts, payments, databases, mobile
apps, teams, dashboards, or anything that sounds like a full product.

Example:

```markdown
# Scope

Build only a very small first demo.

The app should:
- open in a browser
- have one page
- let me type a note
- save notes in the browser
- show saved notes
- let me delete a note

Keep the design simple and pleasant.
Keep the plan short enough for a first demo run.
Stop after the first useful working version.
```

Good first demo ideas:

- a mini notes app
- a simple habit tracker
- a tiny recipe list
- a basic personal budget calculator
- a one-page site for a fictional cafe

Avoid big first demos like marketplaces, chat apps, AI assistants, CRMs, social
networks, or anything with login.

## Run OP

Open Terminal in the project folder. The folder should contain only `mission.md`
and `scope.md`.

Run:

```bash
op /op-build --mission-file mission.md --scope-file scope.md --max-build-cycles 1
```

This command tells OP to plan the project first, then do one short build pass.
For a first demo, one pass is a useful safety limit: enough to see whether the
tool works, but not enough to keep the computer busy all day.

When the command finishes, look at what appeared in the folder. OP may create
app files, planning notes, status files, and work notes. If it says the work is
not finished yet, you can run the same command again or ask a technical person
to inspect the result.

This beginner demo assumes the computer has only the normal Codex profile, using
the default `~/.codex/auth.json`. If you have never used Codex from Terminal
before, open Codex and sign in first.

## What must be installed

For the simplest Mac demo, the computer needs:

- OP installed, so `op` works in Terminal
- Codex signed in on that computer
- Python 3.11 or newer
- Git
- Bash

Most Macs already have Bash. Git is often available after installing Apple's
developer command line tools. If `git` is missing, macOS usually offers to
install those tools the first time you type:

```bash
git --version
```

## Clone OP and install it globally

If someone already gave you access to the OP repository, run these commands in
Terminal one by one:

```bash
cd ~
mkdir -p projects
cd projects
git clone https://github.com/slobodanmargetic988/Optimus-Prime-GSD-Fusion.git
cd Optimus-Prime-GSD-Fusion
python3 -m scripts.release.build_lane_c_bundle --repo-root "$PWD" --out-dir dist --version 0.3.0-rc.2-local-demo
python3 scripts/install/op_install.py --bundle-dir dist/optimus-prime-0.3.0-rc.2-local-demo --mode global
export PATH="$HOME/.local/bin:$PATH"
opctl doctor
```

After this, `op` should work from any project folder in Terminal.
