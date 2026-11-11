# Elfbot 3000

Takes a list of people from a CSV file and randomly generates secret santa mappings.
Sends text messages (SMS) to everyone. That's it.
Also it supports exclusions: `NotWith` lists people (separated by `|`) the giver must not draw, e.g. their partner.
Also it's anonymous, the organizer won't know who has whom.

_NOTE: Requires Twilio account_

## Setup

Set up the necessary environment variables with your information from the Twilio dashboard.
Put them into `twilio.env` and execute `source twilio.env`

Install dependencies via `pipenv install --dev` (Python 3.13)

## CSV format

```
Name,PhoneNumber,NotWith,Language
Buffalo,+456123789,Mortimer|Otto,en
Mortimer,+123789456,,en
Otto,+237894561,Wilson,en
Wilson,+123456789,Otto,de
```

Exclusions are one-way: here Otto won't draw Wilson and Wilson won't draw Otto, but Mortimer could still draw Buffalo.
`Language` is optional (`en` or `de`, default `en`).

## How to run

Execute tests via `pipenv run pytest`.

Do a dry run (no Twilio env vars needed, prints who has whom): `pipenv run python send_secret_santas.py <your file>.csv -d`

Send a test message to everyone: `pipenv run python send_secret_santas.py <your file>.csv -t`

Do the real thing: `pipenv run python send_secret_santas.py <your file>.csv`

## Resending

Every run prints a seed. If some messages fail, the script prints a command that resends just those, using the same seed so nobody gets a different person.
It only works if the CSV is unchanged (same people, same order). Anyone with the seed can see all pairs via a dry run, so keep it to yourself.

```
pipenv run python send_secret_santas.py <your file>.csv --seed 123 --only 'Otto,Wilson'
```
