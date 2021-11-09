import pytest
from secret_santa_generator import SecretSantaGenerator


def person_from(name, group_Id):
    return {'name': name, 'group_Id': group_Id}


def test_individuals():
    people = [
        person_from('Test 1', 1),
        person_from('Test 2', 2),
        person_from('Test 3', 3),
    ]

    mapping = SecretSantaGenerator().generate_mapping(people)

    for pair in mapping:
        assert pair['giver']['name'] != pair['receiver']['name']


def test_couples():
    people = [
        person_from('Test 1', 1),
        person_from('Test 2', 1),
        person_from('Test 3', 2),
        person_from('Test 3', 2),
    ]

    mapping = SecretSantaGenerator().generate_mapping(people)

    for pair in mapping:
        assert pair['giver']['group_Id'] != pair['receiver']['group_Id']
