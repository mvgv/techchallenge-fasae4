import sys
from pathlib import Path

import fakeredis
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import preflight_demo as pf  # noqa: E402

from medwatch.config import Settings  # noqa: E402


def test_stream_groups_match_workers():
    from medwatch.alerts import worker as alerts
    from medwatch.anomaly import worker as anomaly
    from medwatch.audio import worker as audio
    from medwatch.fusion import worker as fusion
    from medwatch.text import worker as text
    from medwatch.video import worker as video
    mods = (alerts, anomaly, audio, fusion, text, video)
    for mod in mods:
        for stream in mod.STREAMS:
            if stream in pf.STREAM_GROUPS:
                assert pf.STREAM_GROUPS[stream] == mod.GROUP
    assert set(pf.STREAM_GROUPS.values()) == {m.GROUP for m in mods}


def client(handler):
    return httpx.Client(base_url="http://t", transport=httpx.MockTransport(handler))


def test_api_ok_and_down():
    assert pf.check_api(client(lambda r: httpx.Response(200, json={}))).ok
    assert not pf.check_api(client(lambda r: httpx.Response(500))).ok

    def boom(_r):
        raise httpx.ConnectError("x")
    assert not pf.check_api(client(boom)).ok


def test_workers_missing_groups():
    r = fakeredis.FakeRedis(decode_responses=True)
    res = pf.check_workers(r)
    assert res and not any(x.ok for x in res)


def test_workers_with_consumer():
    r = fakeredis.FakeRedis(decode_responses=True)
    for stream, group in pf.STREAM_GROUPS.items():
        r.xgroup_create(stream, group, id="0", mkstream=True)
        r.xadd(stream, {"a": "1"})
        r.xreadgroup(group, "c1", {stream: ">"}, count=1)
    assert all(x.ok for x in pf.check_workers(r))


def test_fake_azure_lists_human_items():
    s = Settings(use_fake_azure=True, teams_webhook_url="", logic_app_email_url="")
    res = pf.check_azure(s) + pf.check_alert_channels(s)
    failed = [x for x in res if not x.ok]
    assert failed and all(x.human for x in failed)


def test_real_azure_requires_keys_and_calls():
    s = Settings(use_fake_azure=False, azure_speech_key="k", azure_language_key="k",
                 azure_language_endpoint="https://e")
    calls = []
    res = pf.check_azure(s, lambda: calls.append(1))
    assert all(x.ok for x in res) and calls
    res = pf.check_azure(Settings(use_fake_azure=False), lambda: calls.append(2))
    assert not res[0].ok and calls == [1]


def test_send_test_uses_channels():
    sent = []

    def handler(req):
        sent.append(str(req.url))
        return httpx.Response(200)
    s = Settings(teams_webhook_url="https://teams/x", logic_app_email_url="https://logic/y",
                 alert_email_to="a@b.c")
    res = pf.check_alert_channels(s, send_test=True, transport=httpx.MockTransport(handler))
    assert all(x.ok for x in res) and len(sent) == 2


def test_files(tmp_path):
    (tmp_path / "s").mkdir()
    (tmp_path / "m").mkdir()
    assert not any(x.ok for x in pf.check_files(tmp_path / "s", tmp_path / "m"))
    for f in pf.REQUIRED_SAMPLES:
        (tmp_path / "s" / f).write_text("x")
    for f in pf.REQUIRED_MODELS:
        (tmp_path / "m" / f).write_text("x")
    assert all(x.ok for x in pf.check_files(tmp_path / "s", tmp_path / "m"))


@pytest.mark.parametrize("alerts,evidence,pid,ok", [
    ([], [], "P-0001", True), ([{"a": 1}], [], "P-0001", False),
    ([], [{"e": 1}], "P-0001", False), ([], [], "T-0001", False)])
def test_clean_db(alerts, evidence, pid, ok):
    def handler(req):
        path = req.url.path
        if path == "/patients":
            return httpx.Response(200, json=[{"patient_id": pid}])
        if path == "/alerts":
            return httpx.Response(200, json=alerts)
        return httpx.Response(200, json=evidence)
    assert pf.check_clean_db(client(handler)).ok is ok


def test_report_exit_code(capsys):
    assert pf.report([pf.Result(True, "a")]) == 0
    assert pf.report([pf.Result(True, "a"), pf.Result(False, "b", human=True)]) == 1
    assert "Dependem do humano: b" in capsys.readouterr().out
