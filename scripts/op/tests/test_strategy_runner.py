import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "strategy_runner.py"
SCRIPT_DIR = SCRIPT_PATH.parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_ROOT.parent
for candidate in (REPO_ROOT, SCRIPTS_ROOT, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

SPEC = importlib.util.spec_from_file_location("strategy_runner_module", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_manifest(root: Path) -> Path:
    manifest_path = root / "strategy" / "STRATEGY_MANIFEST.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                "# Strategy Manifest",
                "",
                "Please inspect the repo docs yourself and figure out what matters.",
                "- Start with README.md.",
                "- Look at docs/ when useful.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def test_resolve_strategy_manifest_source_reads_manifest_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifest_path = write_manifest(root)

        source = MODULE.resolve_strategy_manifest_source(repo_root=root)

        assert source.mode == "file"
        assert source.path == manifest_path.resolve()
        assert source.display == str(manifest_path.resolve())
        assert source.text is None


def test_resolve_strategy_manifest_source_accepts_inline_manifest_text():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        source = MODULE.resolve_strategy_manifest_source(
            repo_root=root,
            manifest="# Inline Manifest\n\nRead README.md first.\n",
        )

        assert source.mode == "inline"
        assert source.path is None
        assert source.display == MODULE.INLINE_STRATEGY_MANIFEST_LABEL
        assert "Read README.md first." in (source.text or "")


def test_resolve_strategy_manifest_source_rejects_inline_and_file_together():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_manifest(root)

        with pytest.raises(MODULE.StrategyRunnerError, match="provide either inline strategy manifest text or strategy_manifest_file"):
            MODULE.resolve_strategy_manifest_source(
                repo_root=root,
                manifest="# Inline Manifest\n",
                manifest_file="strategy/STRATEGY_MANIFEST.md",
            )


def test_run_strategy_writes_packet_and_summary_from_manifest_file(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_manifest(root)

        def fake_run_codex_exec(*, repo_root, prompt_text, output_last_message, stdout_path, stderr_path, codex_home=None):
            del codex_home
            assert "Read that manifest file first" in prompt_text
            assert str((root / "strategy" / "STRATEGY_MANIFEST.md").resolve()) in prompt_text
            assert "Do not rely on the caller to pre-collect context for you." in prompt_text
            packet_path = repo_root / "strategy" / "current" / "strategy_packet.md"
            summary_path = repo_root / "strategy" / "current" / "STRATEGY_SUMMARY.md"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Strategic Summary\n\nPacket content.\n", encoding="utf-8")
            summary_path.write_text("# Summary\n\nSummary content.\n", encoding="utf-8")
            output_last_message.write_text(
                "Wrote strategy/current/strategy_packet.md and strategy/current/STRATEGY_SUMMARY.md\n",
                encoding="utf-8",
            )
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)

        result = MODULE.run_strategy(repo_root=root)

        assert result.manifest_ref == str((root / "strategy" / "STRATEGY_MANIFEST.md").resolve())
        assert result.packet_path.exists()
        assert result.summary_path.exists()
        assert "Packet content." in result.packet_path.read_text(encoding="utf-8")
        assert "Summary content." in result.summary_path.read_text(encoding="utf-8")


def test_run_strategy_accepts_inline_manifest_text(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        def fake_run_codex_exec(*, repo_root, prompt_text, output_last_message, stdout_path, stderr_path, codex_home=None):
            del codex_home
            assert "The full manifest was provided inline below." in prompt_text
            assert "# Inline Manifest" in prompt_text
            packet_path = repo_root / "strategy" / "current" / "strategy_packet.md"
            summary_path = repo_root / "strategy" / "current" / "STRATEGY_SUMMARY.md"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Strategic Summary\n\nInline packet.\n", encoding="utf-8")
            summary_path.write_text("# Summary\n\nInline summary.\n", encoding="utf-8")
            output_last_message.write_text("Wrote both strategy markdown files.\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)

        result = MODULE.run_strategy(
            repo_root=root,
            manifest="# Inline Manifest\n\nInspect README.md and the docs folder if needed.\n",
        )

        assert result.manifest_ref == MODULE.INLINE_STRATEGY_MANIFEST_LABEL
        assert result.packet_path.exists()
        assert result.summary_path.exists()


def test_run_strategy_retries_until_required_files_exist(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_manifest(root)
        attempts: list[str] = []

        def fake_run_codex_exec(*, repo_root, prompt_text, output_last_message, stdout_path, stderr_path, codex_home=None):
            del codex_home
            attempts.append(prompt_text)
            packet_path = repo_root / "strategy" / "current" / "strategy_packet.md"
            summary_path = repo_root / "strategy" / "current" / "STRATEGY_SUMMARY.md"
            if len(attempts) == 1:
                packet_path.parent.mkdir(parents=True, exist_ok=True)
                packet_path.write_text("# Strategic Summary\n\nFirst attempt.\n", encoding="utf-8")
                output_last_message.write_text(
                    "I only wrote strategy/current/strategy_packet.md\n",
                    encoding="utf-8",
                )
                stdout_path.write_text("", encoding="utf-8")
                stderr_path.write_text("", encoding="utf-8")
                return 0
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Strategic Summary\n\nSecond attempt.\n", encoding="utf-8")
            summary_path.write_text("# Summary\n\nNow present.\n", encoding="utf-8")
            output_last_message.write_text(
                "Wrote strategy/current/strategy_packet.md and strategy/current/STRATEGY_SUMMARY.md\n",
                encoding="utf-8",
            )
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)

        result = MODULE.run_strategy(repo_root=root)

        assert len(attempts) == 2
        assert "Previous attempt issues:" in attempts[1]
        assert "strategy/current/STRATEGY_SUMMARY.md" in attempts[1]
        assert result.summary_path.exists()


def test_run_strategy_fails_when_llm_never_writes_required_files(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_manifest(root)

        def fake_run_codex_exec(*, repo_root, prompt_text, output_last_message, stdout_path, stderr_path, codex_home=None):
            del repo_root, prompt_text, codex_home
            output_last_message.write_text("I did not create the files.\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)

        with pytest.raises(MODULE.StrategyRunnerError, match="outputs were not written after 3 attempts"):
            MODULE.run_strategy(repo_root=root)
