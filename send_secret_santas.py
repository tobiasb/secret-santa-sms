import argparse
import csv
import json
import os
import random
import shlex
import sys
import urllib.error
import urllib.request

from twilio.rest import Client

from secret_santa_generator import SecretSantaGenerator

CHANNELS = ("sms", "signal")
REQUIRED_COLUMNS = ("name", "phonenumber", "notwith")
OPTIONAL_COLUMNS = ("language", "channel")


def read_participants(file_name):
    """Column names are matched ignoring case and surrounding spaces."""
    people = []

    with open(file_name) as csv_file:
        reader = csv.reader(csv_file)
        header = [h.strip().lower() for h in next(reader, [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        unknown = [h for h in header if h not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
        if missing or unknown:
            raise ValueError(
                "Bad CSV header. Missing: {}. Unknown: {}. See README.md for the format.".format(
                    ", ".join(missing) or "none", ", ".join(unknown) or "none"
                )
            )

        for values in reader:
            row = dict(zip(header, values))
            name = row["name"].strip()
            channel = (row.get("channel") or "sms").strip().lower()
            if channel not in CHANNELS:
                raise ValueError(
                    "{} has unknown Channel '{}', use sms or signal".format(name, channel)
                )
            people.append(
                {
                    "name": name,
                    "phone_number": row["phonenumber"].strip(),
                    "not_withs": [n.strip() for n in row["notwith"].split("|") if n.strip()],
                    "language": (row.get("language") or "en").strip(),
                    "channel": channel,
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


def make_twilio_sender(account_sid, auth_token, from_number):
    client = Client(account_sid, auth_token)

    def send(to, body):
        client.messages.create(body=body, from_=from_number, to=to)

    return send


def make_signal_sender(api_url, from_number):
    """Sends via signal-cli-rest-api."""

    def send(to, body):
        request = urllib.request.Request(
            api_url.rstrip("/") + "/v2/send",
            data=json.dumps({"message": body, "number": from_number, "recipients": [to]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            raise RuntimeError("Signal API HTTP {}: {}".format(e.code, detail)) from e

    return send


def build_senders(channels, env):
    """Returns ({channel: send(to, body)}, []) or (None, [missing env var names])."""
    signal_from = env.get("SIGNAL_SENDER_NUMBER") or env.get("TWILIO_SENDER_PHONE_NUMBER")
    required = {
        "sms": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SENDER_PHONE_NUMBER"],
        "signal": ["SIGNAL_API_URL"],
    }
    missing = [var for channel in channels for var in required[channel] if not env.get(var)]
    if "signal" in channels and not signal_from:
        missing.append("SIGNAL_SENDER_NUMBER")
    if missing:
        return None, missing

    senders = {}
    if "sms" in channels:
        senders["sms"] = make_twilio_sender(
            env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"], env["TWILIO_SENDER_PHONE_NUMBER"]
        )
    if "signal" in channels:
        senders["signal"] = make_signal_sender(env["SIGNAL_API_URL"], signal_from)
    return senders, []


def send_messages(pairs, senders, testrun):
    """Sends one message per pair over the giver's channel. Returns the giver names whose send failed."""
    failed = []
    for pair in pairs:
        giver = pair["giver"]
        try:
            senders[giver["channel"]](giver["phone_number"], message_body(pair, testrun))
            print("🎁 Message sent to {} via {}!".format(giver["name"], giver["channel"]))
        except Exception as e:
            print("💥 Failed to send to {} via {}: {}".format(giver["name"], giver["channel"], e))
            failed.append(giver["name"])
    return failed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generates secret santa mappings and notifies people via sms or signal"
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


def main(argv=None, env=None):
    args = parse_args(argv)
    env = os.environ if env is None else env

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    participants = read_participants(args.participants_file)
    mapping = SecretSantaGenerator().generate_mapping(participants, random.Random(seed))
    pairs = select_pairs(mapping, args.only)

    if args.dryrun:
        print("Dry run (seed {})".format(seed))
        for pair in pairs:
            print(
                "{} is buying a gift for {} (via {})".format(
                    pair["giver"]["name"], pair["receiver"]["name"], pair["giver"]["channel"]
                )
            )
        return 0

    channels = sorted({pair["giver"]["channel"] for pair in pairs})
    senders, missing = build_senders(channels, env)
    if missing:
        print("Error: Make sure the following env vars are set: {}".format(", ".join(missing)))
        return 1

    if args.testrun:
        print("Test run")
    print("🌱 Seed: {} (keep this to resend without reshuffling)".format(seed))

    failed = send_messages(pairs, senders, args.testrun)
    if failed:
        print(
            "\n⚠️  {} failed. Fix the problem, then resend only to them:\n"
            "pipenv run python send_secret_santas.py {} --seed {} --only {}{}".format(
                len(failed),
                shlex.quote(str(args.participants_file)),
                seed,
                shlex.quote(",".join(failed)),
                " -t" if args.testrun else "",
            )
        )
        return 1
    print("🎄 All {} messages sent!".format(len(pairs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
