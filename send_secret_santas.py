import argparse
import csv
import os
import requests

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
                    "group_Id": row["GroupId"],
                    "language": row.get("Language", "en"),
                }
            )
    return people


blurbs = {
    "test": {
        "en": "👋 This is a test message from Elfbot 3000. Beep Boop. 🧝🤖",
        "de": "Dies ist eine Test-Nachricht vom Weihnachtsroboter 3000. Beep. Beep.",
    },
    "real": {
        "en": "Hello {} 👋. This is Elfbot 3000. You are {}'s secret Santa! 🧝🤖💜🎄",
        "de": "Hallo {} 👋. Hier ist der Weihnachtsroboter 3000. Du bist {}'s Wichtelpartner!",
    },
}


def _send_message(signal_api_host, message, from_number, to_number):
    url = "{}/v2/send".format(signal_api_host)
    payload = {"message": message, "number": from_number, "recipients": [to_number]}
    headers = {"Content-Type": "application/json"}
    response = requests.request("POST", url, headers=headers, json=payload)
    
    if response.status_code >= 400:
        print(f"Error sending message to {to_number}: {message}\n{response.text}")

    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generates secret santa mappings and notifies people via sms")
    parser.add_argument("participants_file", help="path to csv file. See README.md for format")
    parser.add_argument("--signal-cli-api-host", required=True, help="signal cli api host")
    parser.add_argument("--from-number", required=True, help="phone number to send from")
    parser.add_argument("-d", "--dryrun", help="does not actually send the text message", action="store_true")
    parser.add_argument("-t", "--testrun", help="sends a test text message", action="store_true")
    args = parser.parse_args()

    participants = read_participants(args.participants_file)
    mapping = SecretSantaGenerator().generate_mapping(participants)

    if args.dryrun:
        print("Dry run")

    if args.testrun:
        print("Test run")

    for pair in mapping:
        if args.dryrun:
            print("{} is buying a gift for {}".format(pair["giver"]["name"], pair["receiver"]["name"]))
        else:
            if args.testrun:
                body = blurbs["test"][pair["giver"]["language"]]
            else:
                body = blurbs["real"][pair["giver"]["language"]].format(
                    pair["giver"]["name"], pair["receiver"]["name"]
                )
            _send_message(args.signal_cli_api_host, body, args.from_number, pair["giver"]["phone_number"])
            print(f"Message sent to {pair['giver']['phone_number']}!")
