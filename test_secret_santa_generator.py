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
