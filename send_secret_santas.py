import argparse
import csv
import os

from twilio.rest import Client

from secret_santa_generator import SecretSantaGenerator


def read_participants(file_name):
    people = []

    with open(file_name) as cvs_file:
        csv_reader = csv.DictReader(cvs_file)
        row_count = 0
        for row in csv_reader:
            if row_count == 1:
                continue
            people.append(
                {
                    "name": row["Name"],
                    "phone_number": row["PhoneNumber"],
                    "not_withs": row["NotWith"].split("|"),
                    "language": row.get("Language", "en"),
                }
            )
    return people


blurbs = {
    "test": {
        "en": "This is a test message from Elfbot 3000. Beep Boop.",
        "de": "Dies ist eine Test-Nachricht vom Weihnachtsroboter 3000. Beep. Beep.",
    },
    "real": {
        "en": "Hello {}. This is Elfbot 3000. You are {}'s secret Santa!",
        "de": "Hallo {}. Hier ist der Weihnachtsroboter 3000. Du bist {}'s Wichtelpartner!",
    },
}


if __name__ == "__main__":

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_SENDER_PHONE_NUMBER")

    if not account_sid or not auth_token or not from_number:
        print(
            "Error: Make sure the following env vars are set: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SENDER_PHONE_NUMBER"
        )
        exit(1)

    parser = argparse.ArgumentParser(
        description="Generates secret santa mappings and notifies people via sms"
    )
    parser.add_argument(
        "participants_file", help="path to csv file. See README.md for format"
    )
    parser.add_argument(
        "-d",
        "--dryrun",
        help="does not actually send the text message",
        action="store_true",
    )
    parser.add_argument(
        "-t", "--testrun", help="sends a test text message", action="store_true"
    )
    args = parser.parse_args()

    participants = read_participants(args.participants_file)
    mapping = SecretSantaGenerator().generate_mapping(participants)

    if args.dryrun:
        print("Dry run")

    if args.testrun:
        print("Test run")

    for pair in mapping:
        if args.dryrun:
            print(
                "{} is buying a gift for {}".format(
                    pair["giver"]["name"], pair["receiver"]["name"]
                )
            )
        else:
            if args.testrun:
                body = blurbs["test"][pair["giver"]["language"]]
            else:
                body = blurbs["real"][pair["giver"]["language"]].format(
                    pair["giver"]["name"], pair["receiver"]["name"]
                )
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=body, from_=from_number, to=pair["giver"]["phone_number"]
            )
            print("Message sent!")
