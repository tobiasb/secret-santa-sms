import random

MAX_ATTEMPTS = 100_000


class SecretSantaGenerator:
    @staticmethod
    def validate_participants(participants):
        names = [p["name"] for p in participants]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError("Duplicate names: {}".format(", ".join(sorted(dupes))))
        for p in participants:
            unknown = [n for n in p["not_withs"] if n not in names]
            if unknown:
                raise ValueError(
                    "{} has unknown NotWith names: {}".format(p["name"], ", ".join(unknown))
                )

    @staticmethod
    def validate_mapping(population, mapping):
        for i in range(0, len(mapping)):
            giver = population[i]
            receiver = population[mapping[i]]
            if i == mapping[i] or receiver["name"] in giver["not_withs"]:
                return False
        return True

    def generate_mapping(self, participants, rng=None):
        """Same participants (in the same order) and same seeded rng give the same mapping."""
        rng = rng or random.Random()
        self.validate_participants(participants)
        participants = list(participants)
        rng.shuffle(participants)

        for _ in range(MAX_ATTEMPTS):
            current_mapping = rng.sample(
                range(0, len(participants)), len(participants)
            )
            if self.validate_mapping(participants, current_mapping):
                return [
                    {"giver": participants[i], "receiver": participants[current_mapping[i]]}
                    for i in range(0, len(participants))
                ]

        raise ValueError(
            "No valid mapping found after {} attempts. Are the NotWith lists too strict?".format(
                MAX_ATTEMPTS
            )
        )
