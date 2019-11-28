import pytest
from secret_santa_generator import SecretSantaGenerator


def person_from(name, couple_id):
    return {'name': name, 'couple_id': couple_id}


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
        assert pair['giver']['couple_id'] != pair['receiver']['couple_id']