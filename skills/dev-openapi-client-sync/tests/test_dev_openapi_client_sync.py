import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev_openapi_client_sync.py"
SPEC = importlib.util.spec_from_file_location("dev_openapi_client_sync", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeRunner(MODULE.CommandRunner):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, cmd, cwd, env=None):
        self.calls.append((cmd, cwd, env or {}))
        if self.responses:
            return self.responses.pop(0)
        return MODULE.CmdResult(1, "", "unexpected command")


def cfg(root: Path, **overrides):
    openapi_output = overrides.get("openapi_output", root / "tmp" / "openapi.json")
    client_root = overrides.get("client_root", root / "web" / "nuxt-app")
    client_root.mkdir(parents=True, exist_ok=True)
    (client_root / "generated.ts").write_text("v1\n", encoding="utf-8")
    return MODULE.SyncInput(
        repo_root=root,
        openapi_output=openapi_output,
        client_root=client_root,
        generate_command=overrides.get("generate_command", "python3 -c \"print('gen')\""),
        export_command=overrides.get("export_command", "python3 -c \"print('export')\""),
        base_url_override=overrides.get("base_url_override", None),
        fail_on_drift=overrides.get("fail_on_drift", False),
        dry_run=overrides.get("dry_run", False),
    )


class DevOpenApiClientSyncTests(unittest.TestCase):
    def test_render_command_allows_literal_json_braces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = cfg(root)
            cmd = MODULE.render_command(
                "python3 -c \"print('{\\\"openapi\\\":\\\"3.0.0\\\",\\\"paths\\\":{}}')\"",
                c,
            )
            self.assertEqual(cmd[0], "python3")

    def test_render_command_rejects_unknown_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = cfg(root)
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.render_command("python3 -c \"print('{unknown_token}')\"", c)
            self.assertEqual(ctx.exception.code, "input_error")

    def test_changed_file_detection_unit(self):
        before = {"a.ts": "h1", "b.ts": "h2"}
        after = {"a.ts": "h1", "b.ts": "h3", "c.ts": "h4"}
        changed = MODULE.changed_files(before, after)
        self.assertEqual(changed, ["b.ts", "c.ts"])

    def test_integration_fixture_schema_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client_root = root / "web" / "nuxt-app"
            client_root.mkdir(parents=True, exist_ok=True)
            target = client_root / "generated.ts"
            target.write_text("old\n", encoding="utf-8")

            export_py = root / "export.py"
            export_py.write_text(
                "import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--out');a=p.parse_args();Path(a.out).parent.mkdir(parents=True, exist_ok=True);Path(a.out).write_text('{\\\"openapi\\\":\\\"3.0.0\\\"}\\n',encoding='utf-8')\n",
                encoding="utf-8",
            )
            gen_py = root / "generate.py"
            gen_py.write_text(
                "import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--file');a=p.parse_args();Path(a.file).write_text('new\\n',encoding='utf-8')\n",
                encoding="utf-8",
            )

            openapi_output = root / "tmp" / "openapi.json"
            generate_command = f"{sys.executable} {gen_py} --file {target}"
            export_command = f"{sys.executable} {export_py} --out {openapi_output}"

            out = MODULE.execute(
                MODULE.SyncInput(
                    repo_root=root,
                    openapi_output=openapi_output,
                    client_root=client_root,
                    generate_command=generate_command,
                    export_command=export_command,
                    base_url_override=None,
                    fail_on_drift=False,
                    dry_run=False,
                ),
                runner=MODULE.CommandRunner(),
            )

            self.assertTrue(out["ok"])
            self.assertTrue(out["openapi_generated"])
            self.assertTrue(out["client_generated"])
            self.assertTrue(out["drift_detected"])
            self.assertIn("generated.ts", out["changed_files"])

    def test_missing_npm_dependency_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = cfg(root)
            runner = FakeRunner(
                [
                    MODULE.CmdResult(0, "", ""),
                    MODULE.CmdResult(1, "", "npm ERR! missing script: generate:api"),
                ]
            )
            out = MODULE.execute(c, runner=runner)
            self.assertFalse(out["ok"])
            self.assertEqual(out["errors"][0]["code"], "env")

    def test_fail_on_drift_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = cfg(root, fail_on_drift=True)

            class DriftRunner(MODULE.CommandRunner):
                def run(self, cmd, cwd, env=None):
                    if "export" in " ".join(cmd):
                        c.openapi_output.parent.mkdir(parents=True, exist_ok=True)
                        c.openapi_output.write_text("{}", encoding="utf-8")
                    else:
                        (c.client_root / "generated.ts").write_text("changed\n", encoding="utf-8")
                    return MODULE.CmdResult(0, "", "")

            out = MODULE.execute(c, runner=DriftRunner())
            self.assertFalse(out["ok"])
            codes = {e["code"] for e in out["errors"]}
            self.assertIn("drift_detected", codes)

    def test_output_contract_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = cfg(root, dry_run=True)
            out = MODULE.execute(c, runner=FakeRunner([]))
            required = {
                "ok",
                "tool",
                "openapi_generated",
                "client_generated",
                "changed_files",
                "drift_detected",
                "warnings",
                "errors",
            }
            self.assertTrue(required.issubset(set(out.keys())))


if __name__ == "__main__":
    unittest.main()
