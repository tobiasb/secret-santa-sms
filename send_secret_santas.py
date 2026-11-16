import argparse
import csv
import json
import os
import random
import shlex
import sys
import time
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


SMS_DELIVERY_WAIT_SECONDS = 30
SMS_DELIVERY_POLL_SECONDS = 3


class TwilioSender:
    """Twilio accepts a message first and can fail it later (e.g. error 30034), so check_delivery polls."""

    def __init__(self, account_sid, auth_token, from_number):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number

    def __call__(self, to, body):
        """Returns the message SID."""
        return self.client.messages.create(body=body, from_=self.from_number, to=to).sid

    def check_delivery(self, sids):
        """Takes {name: sid}. Returns ({name: reason} failed, [names] still unconfirmed at the deadline)."""
        failed = {}
        pending = dict(sids)
        deadline = time.monotonic() + SMS_DELIVERY_WAIT_SECONDS
        while pending and time.monotonic() < deadline:
            time.sleep(SMS_DELIVERY_POLL_SECONDS)
            for name, sid in list(pending.items()):
                message = self.client.messages(sid).fetch()
                if message.status == "delivered":
                    del pending[name]
                elif message.status in ("failed", "undelivered"):
                    reason = "Twilio says {}, error {}".format(message.status, message.error_code)
                    if message.error_code == 30034:
                        reason += " (US number? set its Channel to signal)"
                    failed[name] = reason
                    del pending[name]
        return failed, sorted(pending)


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
        senders["sms"] = TwilioSender(
            env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"], env["TWILIO_SENDER_PHONE_NUMBER"]
        )
    if "signal" in channels:
        senders["signal"] = make_signal_sender(env["SIGNAL_API_URL"], signal_from)
    return senders, []


def send_messages(pairs, senders, testrun):
    """Sends one message per pair over the giver's channel. Returns the giver names whose send failed."""
    failed = []
    receipts = {}
    for pair in pairs:
        giver = pair["giver"]
        channel = giver["channel"]
        try:
            receipt = senders[channel](giver["phone_number"], message_body(pair, testrun))
            receipts.setdefault(channel, {})[giver["name"]] = receipt
            print("🎁 Message sent to {} via {}!".format(giver["name"], channel))
        except Exception as e:
            print("💥 Failed to send to {} via {}: {}".format(giver["name"], channel, e))
            failed.append(giver["name"])

    for channel, sent in receipts.items():
        check = getattr(senders[channel], "check_delivery", None)
        if not check:
            continue
        print("⏳ Checking {} delivery (up to {}s)...".format(channel, SMS_DELIVERY_WAIT_SECONDS))
        try:
            undelivered, unconfirmed = check(sent)
        except Exception as e:
            print("⚠️  Couldn't check {} delivery: {}".format(channel, e))
            continue
        for name, reason in undelivered.items():
            print("💥 {} didn't get it via {}: {}".format(name, channel, reason))
            failed.append(name)
        if unconfirmed:
            print("🤷 Not confirmed delivered yet, check Twilio's logs: {}".format(", ".join(unconfirmed)))
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
