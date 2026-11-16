# Elfbot 3000

Takes a list of people from a CSV file and randomly generates secret santa mappings.
Sends everyone a message by SMS (Twilio) or Signal ([signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api)). That's it.
Also it supports exclusions: `NotWith` lists people (separated by `|`) the giver must not draw, e.g. their partner.
Also it's anonymous, the organizer won't know who has whom.

_NOTE: Requires a Twilio account for SMS and/or a signal-cli-rest-api instance for Signal_

## Setup

Copy `elfbot.env.template` to `elfbot.env`, fill it in and execute `source elfbot.env`.
Only the channels used in the CSV need their variables: Twilio for `sms`, `SIGNAL_API_URL` for `signal`.
`SIGNAL_SENDER_NUMBER` defaults to `TWILIO_SENDER_PHONE_NUMBER`.

Install dependencies via `pipenv install --dev` (Python 3.13)

## CSV format

```
Name,PhoneNumber,NotWith,Language,Channel
Buffalo,+456123789,Mortimer|Otto,en,sms
Mortimer,+123789456,,en,sms
Otto,+237894561,Wilson,en,signal
Wilson,+123456789,Otto,de,
```

Exclusions are one-way: here Otto won't draw Wilson and Wilson won't draw Otto, but Mortimer could still draw Buffalo.
`Language` is optional (`en` or `de`, default `en`).
`Channel` is optional (`sms` or `signal`, default `sms`). Test runs and resends use it too.
Use `signal` for US numbers if your Twilio number isn't A2P 10DLC registered: Twilio blocks those texts (error 30034).

## How to run

Execute tests via `pipenv run pytest`.

Do a dry run (no env vars needed, prints who has whom): `pipenv run python send_secret_santas.py <your file>.csv -d`

Send a test message to everyone: `pipenv run python send_secret_santas.py <your file>.csv -t`

Do the real thing: `pipenv run python send_secret_santas.py <your file>.csv`

## Resending

Every run prints a seed. If some messages fail, the script prints a command that resends just those, using the same seed so nobody gets a different person.
The pairs stay the same as long as `Name`, `NotWith` and the row order don't change. Fixing a `PhoneNumber` or switching someone's `Channel` before resending is fine.
Anyone with the seed can see all pairs via a dry run, so keep it to yourself.

```
pipenv run python send_secret_santas.py <your file>.csv --seed 123 --only 'Otto,Wilson'
```
