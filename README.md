# Elfbot 3000

Takes a list of people from a CSV file and randomly generates secret santa mappings.
Sends text messages (SMS) to everyone. That's it.
Also it supports "groups". People within a group won't get someone within the same group as secret santa.
Also it's anonymous, the organizer won't know who has whom.

_NOTE: Requires Twilio account_

## Setup

Set up the necessary environment variables with your information from the Twilio dashboard.
Put them into `twilio.env` and execute `source twilio.env`

Install dependencies via `pipenv install`

## CSV format

```
Name,PhoneNumber,NotWith,Language
Buffalo,+456123789,Mortimer,en
Mortimer,+123789456,,en
Otto,+237894561,Wilson,en
Wilson,+123456789,Otto,de
```

In this example, because Mortimer and Otto have the same group ID, they won't get each other as secret santa.

## How to run

Execute tests via `pytest`.

Do a dry run: `pipenv run python send_secret_santas.py <your file>.csv -d`

Send a test message to everyone: `pipenv run python send_secret_santas.py <your file>.csv -t`

Do the real thing: `pipenv run python send_secret_santas.py <your file>.csv`
