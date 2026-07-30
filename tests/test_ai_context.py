from backend.services.ai import _build_api_messages, _build_failure_context


HISTORY = [
    {"role": "user", "content": "Build me a dev machine"},
    {"role": "assistant", "content": "Here's a config."},
    {"role": "user", "content": "The build failed — can you fix it?"},
]

FAILED_BUILD = {
    "status": "failed",
    "progress": 35,
    "step": "Failed",
    "error": "lb build failed with exit code 123\n\nbroadcom-sta-dkms failed to compile "
             "against the live kernel via DKMS inside the chroot.",
    "log_path": "/nonexistent/build.log",
}


def test_failure_context_included():
    messages = _build_api_messages(HISTORY, {"packages": ["broadcom-sta-dkms"]}, FAILED_BUILD)
    last = messages[-1]["content"]
    assert "<latest_build_result>" in last
    assert "broadcom-sta-dkms" in last
    assert "FAILED at 35%" in last
    assert "<current_config_state>" in last
    # the user's actual message is still there, after the context
    assert last.rstrip().endswith("can you fix it?")


def test_failure_context_reads_log_tail(tmp_path):
    log = tmp_path / "build.log"
    log.write_text("downloading...\nP: installing\ndpkg: error processing package broadcom-sta-dkms\nE: build failed\n")
    build = {**FAILED_BUILD, "log_path": str(log)}
    context = _build_failure_context(build)
    assert "dpkg: error processing package broadcom-sta-dkms" in context
    assert "E: build failed" in context


def test_no_context_for_successful_build():
    ok_build = {**FAILED_BUILD, "status": "completed"}
    assert _build_failure_context(ok_build) is None
    messages = _build_api_messages(HISTORY, None, ok_build)
    assert "<latest_build_result>" not in messages[-1]["content"]


def test_no_build_at_all():
    messages = _build_api_messages(HISTORY, None, None)
    assert messages[-1]["content"] == "The build failed — can you fix it?"
