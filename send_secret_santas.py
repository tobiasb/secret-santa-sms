import argparse
import random
import os
import csv
from twilio.rest import Client

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
from_number = os.environ.get('TWILIO_PHONE_NUMBER')


def validate_mapping(population, mapping):
    for i in range(0, len(mapping)):
        giver = population[i]
        givee = population[mapping[i]]
        if i == mapping[i] or giver['couple_id'] == givee['couple_id']:
            return False
    return True


parser = argparse.ArgumentParser(description='Generates secret santa mappings and notifies people via sms')
parser.add_argument('participants_file', help='path to csv file. See README.md for format')
parser.add_argument('-d', '--dryrun', help='does not actually send the text message', action='store_true')
args = parser.parse_args()

participants = []

with open(args.participants_file) as cvs_file:
    csv_reader = csv.DictReader(cvs_file)
    row_count = 0
    for row in csv_reader:
        if row_count == 1:
            continue
        participants.append({
            'name': row['Name'],
            'phone_number': row['PhoneNumber'],
            'couple_id': row['CoupleId'],
        })

print('Shuffling data')
random.shuffle(participants)

current_mapping = []
isValidMapping = False

while not isValidMapping:
    current_mapping = random.sample(range(0, len(participants)), len(participants))
    isValidMapping = validate_mapping(participants, current_mapping)

if args.dryrun:
    print("Dry run")

for i in range(0, len(current_mapping)):
    santa = participants[i]
    santee = participants[current_mapping[i]]

    print('Person {} (couple {}) is secret santa of person {} (couple {})'.format(i, santa['couple_id'], current_mapping[i], santee['couple_id']))

    if not args.dryrun:
        body = u"Hello {}. This is Elfbot 3000. You are {}'s secret Santa!".format(santa['name'], santee['name'])
        client = Client(account_sid, auth_token)
        client.messages.create(body=body, from_=from_number, to=santa['phone_number'])
        print('Message sent!')
