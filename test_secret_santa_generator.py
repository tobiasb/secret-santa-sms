import json
import random
import shlex
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import send_secret_santas
from secret_santa_generator import SecretSantaGenerator
from send_secret_santas import read_participants, select_pairs, send_messages


def person(name, *not_withs):
    return {"name": name, "not_withs": list(not_withs)}


@pytest.mark.parametrize("_", range(50))
def test_no_self_assignment(_):
    people = [person("A"), person("B"), person("C")]

    mapping = SecretSantaGenerator().generate_mapping(people)

    assert len(mapping) == 3
    for pair in mapping:
        assert pair["giver"]["name"] != pair["receiver"]["name"]
    assert sorted(p["receiver"]["name"] for p in mapping) == ["A", "B", "C"]


@pytest.mark.parametrize("_", range(50))
def test_not_withs_respected(_):
    people = [
        person("A", "B"),
        person("B", "A"),
        person("C", "D"),
        person("D", "C"),
    ]

    mapping = SecretSantaGenerator().generate_mapping(people)

    for pair in mapping:
        assert pair["receiver"]["name"] not in pair["giver"]["not_withs"]


def test_impossible_constraints_raise():
    people = [person("A", "B"), person("B")]

    with pytest.raises(ValueError, match="No valid mapping"):
        SecretSantaGenerator().generate_mapping(people)


def test_unknown_not_with_raises():
    people = [person("A", "Bob"), person("B"), person("C")]

    with pytest.raises(ValueError, match="unknown NotWith"):
        SecretSantaGenerator().generate_mapping(people)


def test_duplicate_names_raise():
    people = [person("A"), person("A"), person("B")]

    with pytest.raises(ValueError, match="Duplicate"):
        SecretSantaGenerator().generate_mapping(people)


def test_read_participants(tmp_path):
    csv_file = tmp_path / "people.csv"
    csv_file.write_text(
        "Name,PhoneNumber,NotWith,Language,Channel\n"
        "A,+1,B|C,de,Signal\n"
        "B,+2,,,\n"
        "C,+3,A,en,sms\n"
    )

    people = read_participants(csv_file)

    assert [p["name"] for p in people] == ["A", "B", "C"]
    assert people[0]["not_withs"] == ["B", "C"]
    assert people[0]["language"] == "de"
    assert people[1]["not_withs"] == []
    assert people[1]["language"] == "en"
    assert [p["channel"] for p in people] == ["signal", "sms", "sms"]


def test_read_participants_without_optional_columns(tmp_path):
    csv_file = tmp_path / "people.csv"
    csv_file.write_text("Name,PhoneNumber,NotWith\nA,+1,\nB,+2,\n")

    people = read_participants(csv_file)

    assert all(p["language"] == "en" for p in people)
    assert all(p["channel"] == "sms" for p in people)


def test_read_participants_unknown_channel_raises(tmp_path):
    csv_file = tmp_path / "people.csv"
    csv_file.write_text("Name,PhoneNumber,NotWith,Channel\nA,+1,,whatsapp\n")

    with pytest.raises(ValueError, match="unknown Channel"):
        read_participants(csv_file)


def names(mapping):
    return [(p["giver"]["name"], p["receiver"]["name"]) for p in mapping]


def test_same_seed_same_mapping():
    people = [person(n) for n in "ABCDEFGH"]

    first = SecretSantaGenerator().generate_mapping(people, random.Random(42))
    second = SecretSantaGenerator().generate_mapping(people, random.Random(42))

    assert names(first) == names(second)


def test_select_pairs_only():
    mapping = SecretSantaGenerator().generate_mapping([person(n) for n in "ABC"])

    assert [p["giver"]["name"] for p in select_pairs(mapping, ["B"])] == ["B"]
    assert select_pairs(mapping, []) == mapping
    with pytest.raises(ValueError, match="unknown"):
        select_pairs(mapping, ["Zed"])


def test_send_messages_uses_channel_and_continues_after_failure():
    people = [
        dict(person(n), phone_number="+" + n, language="en", channel=c)
        for n, c in [("A", "sms"), ("B", "sms"), ("C", "signal")]
    ]
    mapping = SecretSantaGenerator().generate_mapping(people)
    sent = []

    def sms(to, body):
        if to == "+B":
            raise RuntimeError("boom")
        sent.append(("sms", to))

    def signal(to, body):
        sent.append(("signal", to))

    failed = send_messages(mapping, {"sms": sms, "signal": signal}, testrun=False)

    assert failed == ["B"]
    assert sorted(sent) == [("signal", "+C"), ("sms", "+A")]


class FakeTwilio:
    """Stands in for twilio.rest.Client. Records sends; fails numbers in fail_to."""

    def __init__(self, fail_to=()):
        self.fail_to = set(fail_to)
        self.sent = {}

    def __call__(self, account_sid, auth_token):
        return self

    @property
    def messages(self):
        return self

    def create(self, body, from_, to):
        assert from_ == "+15550000000"
        if to in self.fail_to:
            raise RuntimeError("HTTP 400: nope")
        self.sent[to] = body


class FakeSignalApi:
    """A real HTTP server speaking signal-cli-rest-api's POST /v2/send."""

    def __init__(self):
        self.fail_to = set()
        self.sent = {}
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert self.path == "/v2/send"
                assert payload["number"] == "+15550000000"
                (to,) = payload["recipients"]
                if to in api.fail_to:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"error":"Unregistered user"}')
                    return
                api.sent[to] = payload["message"]
                self.send_response(201)
                self.end_headers()
                self.wfile.write(b'{"timestamp":"1"}')

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:{}".format(self.server.server_port)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reset(self, fail_to=()):
        self.fail_to = set(fail_to)
        self.sent = {}


FAMILY_CSV = (
    "Name,PhoneNumber,NotWith,Language,Channel\n"
    "A,+1001,B,en,sms\n"
    "B,+1002,A,de,sms\n"
    "C,+1003,D|E,en,\n"
    "D,+1004,C,,sms\n"
    "E,+1005,F,en,signal\n"
    "F,+1006,E,de,signal\n"
)


@pytest.fixture
def signal_api():
    api = FakeSignalApi()
    yield api
    api.server.shutdown()


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys, signal_api):
    csv_file = tmp_path / "people.csv"
    csv_file.write_text(FAMILY_CSV)
    env = {
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_SENDER_PHONE_NUMBER": "+15550000000",
        "SIGNAL_API_URL": signal_api.url,
    }

    def run(argv, twilio, signal_fail_to=(), env_overrides=None):
        monkeypatch.setattr(send_secret_santas, "Client", twilio)
        signal_api.reset(signal_fail_to)
        run_env = dict(env, **(env_overrides or {}))
        run_env = {k: v for k, v in run_env.items() if v is not None}
        code = send_secret_santas.main([str(c) for c in argv], env=run_env)
        return code, capsys.readouterr().out

    run.csv = csv_file
    return run


def test_cli_full_send(cli, signal_api):
    twilio = FakeTwilio()

    code, out = cli([cli.csv], twilio)

    assert code == 0
    assert "All 6 messages sent" in out
    assert sorted(twilio.sent) == ["+1001", "+1002", "+1003", "+1004"]
    assert sorted(signal_api.sent) == ["+1005", "+1006"]
    assert twilio.sent["+1002"].startswith("Hallo B.")
    assert signal_api.sent["+1006"].startswith("Hallo F.")
    assert signal_api.sent["+1005"].startswith("Hello E.")


def test_cli_resend_command_reproduces_failed_messages(cli, signal_api):
    expected_twilio = FakeTwilio()
    cli([cli.csv, "--seed", 99], expected_twilio)
    expected = dict(expected_twilio.sent, **signal_api.sent)

    code, out = cli([cli.csv, "--seed", 99], FakeTwilio(fail_to={"+1002"}), signal_fail_to={"+1005"})

    assert code == 1
    assert "Unregistered user" in out
    resend_line = [l for l in out.splitlines() if l.startswith("pipenv run python")][0]
    resend_argv = shlex.split(resend_line)[4:]

    twilio = FakeTwilio()
    code, out = cli(resend_argv, twilio)

    assert code == 0
    assert dict(twilio.sent, **signal_api.sent) == {k: expected[k] for k in ("+1002", "+1005")}


def test_cli_testrun_honors_channel(cli, signal_api):
    twilio = FakeTwilio()

    code, _ = cli([cli.csv, "-t"], twilio)

    assert code == 0
    assert sorted(twilio.sent) == ["+1001", "+1002", "+1003", "+1004"]
    assert sorted(signal_api.sent) == ["+1005", "+1006"]
    for body in list(twilio.sent.values()) + list(signal_api.sent.values()):
        assert "test message" in body or "Test-Nachricht" in body


def test_cli_dryrun_sends_nothing(cli, signal_api):
    twilio = FakeTwilio()

    code, out = cli([cli.csv, "-d"], twilio, env_overrides={"TWILIO_AUTH_TOKEN": None, "SIGNAL_API_URL": None})

    assert code == 0
    assert out.count("is buying a gift for") == 6
    assert out.count("(via signal)") == 2
    assert twilio.sent == {} and signal_api.sent == {}


def test_cli_missing_env_refuses_to_send(cli, signal_api):
    twilio = FakeTwilio()

    code, out = cli([cli.csv], twilio, env_overrides={"SIGNAL_API_URL": None})

    assert code == 1
    assert "SIGNAL_API_URL" in out
    assert twilio.sent == {} and signal_api.sent == {}


def test_cli_signal_only_needs_no_twilio(cli, signal_api):
    no_twilio = {"TWILIO_ACCOUNT_SID": None, "TWILIO_AUTH_TOKEN": None}

    code, out = cli([cli.csv, "-t", "--only", "E,F"], FakeTwilio(), env_overrides=no_twilio)

    assert code == 0
    assert sorted(signal_api.sent) == ["+1005", "+1006"]


def test_cli_signal_sender_override(cli, signal_api):
    code, out = cli(
        [cli.csv, "-t", "--only", "E"],
        FakeTwilio(),
        env_overrides={"TWILIO_SENDER_PHONE_NUMBER": None, "TWILIO_ACCOUNT_SID": None, "SIGNAL_SENDER_NUMBER": "+15550000000"},
    )

    assert code == 0
    assert list(signal_api.sent) == ["+1005"]
