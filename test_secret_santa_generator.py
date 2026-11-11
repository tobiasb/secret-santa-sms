import random

import pytest

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
        "Name,PhoneNumber,NotWith,Language\n"
        "A,+1,B|C,de\n"
        "B,+2,,\n"
        "C,+3,A,en\n"
    )

    people = read_participants(csv_file)

    assert [p["name"] for p in people] == ["A", "B", "C"]
    assert people[0]["not_withs"] == ["B", "C"]
    assert people[0]["language"] == "de"
    assert people[1]["not_withs"] == []
    assert people[1]["language"] == "en"


def test_read_participants_without_language_column(tmp_path):
    csv_file = tmp_path / "people.csv"
    csv_file.write_text("Name,PhoneNumber,NotWith\nA,+1,\nB,+2,\n")

    people = read_participants(csv_file)

    assert all(p["language"] == "en" for p in people)


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


def test_send_messages_continues_after_failure():
    people = [dict(person(n), phone_number="+" + n, language="en") for n in "ABC"]
    mapping = SecretSantaGenerator().generate_mapping(people)
    sent = []

    def send(to, body):
        if to == "+B":
            raise RuntimeError("boom")
        sent.append(to)

    failed = send_messages(mapping, send, testrun=False)

    assert failed == ["B"]
    assert sorted(sent) == ["+A", "+C"]


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


FAMILY_CSV = (
    "Name,PhoneNumber,NotWith,Language\n"
    "A,+1001,B,en\n"
    "B,+1002,A,de\n"
    "C,+1003,D|E,en\n"
    "D,+1004,C,\n"
    "E,+1005,F,en\n"
    "F,+1006,E,de\n"
)


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    import shlex

    import send_secret_santas

    csv_file = tmp_path / "people.csv"
    csv_file.write_text(FAMILY_CSV)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_SENDER_PHONE_NUMBER", "+15550000000")

    def run(argv, fake):
        monkeypatch.setattr(send_secret_santas, "Client", fake)
        code = send_secret_santas.main([str(c) for c in argv])
        return code, capsys.readouterr().out

    run.csv = csv_file
    run.split = shlex.split
    return run


def test_cli_full_send(cli):
    fake = FakeTwilio()

    code, out = cli([cli.csv], fake)

    assert code == 0
    assert "All 6 messages sent" in out
    assert len(fake.sent) == 6
    assert fake.sent["+1002"].startswith("Hallo B.")
    assert fake.sent["+1004"].startswith("Hello D.")


def test_cli_resend_command_reproduces_failed_messages(cli):
    expected = FakeTwilio()
    cli([cli.csv, "--seed", 99], expected)

    first = FakeTwilio(fail_to={"+1002", "+1005"})
    code, out = cli([cli.csv, "--seed", 99], first)

    assert code == 1
    assert len(first.sent) == 4
    resend_line = [l for l in out.splitlines() if l.startswith("pipenv run python")][0]
    resend_argv = cli.split(resend_line)[4:]

    second = FakeTwilio()
    code, out = cli(resend_argv, second)

    assert code == 0
    assert second.sent == {k: expected.sent[k] for k in ("+1002", "+1005")}


def test_cli_testrun_sends_test_blurb(cli):
    fake = FakeTwilio()

    code, _ = cli([cli.csv, "-t"], fake)

    assert code == 0
    assert all("test message" in b or "Test-Nachricht" in b for b in fake.sent.values())


def test_cli_dryrun_sends_nothing(cli, monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")

    code, out = cli([cli.csv, "-d", "--seed", 5], FakeTwilio())

    assert code == 0
    assert out.count("is buying a gift for") == 6


def test_cli_missing_env_refuses_to_send(cli, monkeypatch):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN")
    fake = FakeTwilio()

    code, out = cli([cli.csv], fake)

    assert code == 1
    assert fake.sent == {}
