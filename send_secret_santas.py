import argparse
import csv
import os
import random
import sys

from twilio.rest import Client

from secret_santa_generator import SecretSantaGenerator


def read_participants(file_name):
    people = []

    with open(file_name) as csv_file:
        for row in csv.DictReader(csv_file):
            people.append(
                {
                    "name": row["Name"].strip(),
                    "phone_number": row["PhoneNumber"].strip(),
                    "not_withs": [n.strip() for n in row["NotWith"].split("|") if n.strip()],
                    "language": (row.get("Language") or "en").strip(),
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


def message_body(pair, testrun):
    language = pair["giver"]["language"]
    if testrun:
        return blurbs["test"][language]
    return blurbs["real"][language].format(pair["giver"]["name"], pair["receiver"]["name"])


def select_pairs(mapping, only):
    if not only:
        return mapping
    givers = {pair["giver"]["name"] for pair in mapping}
    unknown = [name for name in only if name not in givers]
    if unknown:
        raise ValueError("--only has unknown names: {}".format(", ".join(unknown)))
    return [pair for pair in mapping if pair["giver"]["name"] in only]


def send_messages(pairs, send, testrun):
    """Sends one message per pair. Returns the giver names whose send failed."""
    failed = []
    for pair in pairs:
        name = pair["giver"]["name"]
        try:
            send(pair["giver"]["phone_number"], message_body(pair, testrun))
            print("🎁 Message sent to {}!".format(name))
        except Exception as e:
            print("💥 Failed to send to {}: {}".format(name, e))
            failed.append(name)
    return failed


def parse_args(argv=None):
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
    parser.add_argument(
        "--seed",
        type=int,
        help="reuse the seed of an earlier run to get the same mapping",
    )
    parser.add_argument(
        "--only",
        type=lambda s: [n.strip() for n in s.split(",") if n.strip()],
        default=[],
        help="comma-separated giver names to message (use with --seed to resend)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_SENDER_PHONE_NUMBER")

    if not args.dryrun and not (account_sid and auth_token and from_number):
        print(
            "Error: Make sure the following env vars are set: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SENDER_PHONE_NUMBER"
        )
        return 1

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    participants = read_participants(args.participants_file)
    mapping = SecretSantaGenerator().generate_mapping(participants, random.Random(seed))
    pairs = select_pairs(mapping, args.only)

    if args.dryrun:
        print("Dry run (seed {})".format(seed))
        for pair in pairs:
            print("{} is buying a gift for {}".format(pair["giver"]["name"], pair["receiver"]["name"]))
        return 0

    if args.testrun:
        print("Test run")
    print("🌱 Seed: {} (keep this to resend without reshuffling)".format(seed))

    client = Client(account_sid, auth_token)

    def send(to, body):
        client.messages.create(body=body, from_=from_number, to=to)

    failed = send_messages(pairs, send, args.testrun)
    if failed:
        print(
            "\n⚠️  {} failed. Fix the problem, then resend only to them:\n"
            "pipenv run python send_secret_santas.py {} --seed {} --only '{}'{}".format(
                len(failed),
                args.participants_file,
                seed,
                ",".join(failed),
                " -t" if args.testrun else "",
            )
        )
        return 1
    print("🎄 All {} messages sent!".format(len(pairs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
