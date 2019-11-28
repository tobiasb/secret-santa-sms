import random


class SecretSantaGenerator:

    @staticmethod
    def validate_mapping(population, mapping):
        for i in range(0, len(mapping)):
            giver = population[i]
            receiver = population[mapping[i]]
            if i == mapping[i] or giver['couple_id'] == receiver['couple_id']:
                return False
        return True

    def generate_mapping(self, participants):
        random.shuffle(participants)

        current_mapping = []
        is_valid_mapping = False

        while not is_valid_mapping:
            current_mapping = random.sample(range(0, len(participants)), len(participants))
            is_valid_mapping = self.validate_mapping(participants, current_mapping)

        indices = range(0, len(participants))
        return [{'giver': participants[i], 'receiver': participants[current_mapping[i]]} for i in indices]

