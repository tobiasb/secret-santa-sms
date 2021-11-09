# Elfbot 3000

Takes a list of people from a CSV file and randomly generates secret santa mappings.
Sends text messages (SMS) to everyone. That's it.
Also it supports couples so people get someone other than their spouse.
Also it's anonymous, the organizer won't know who has whom.

_NOTE: Requires Twilio account_

## Setup

Set up the necessary environment variables with your information from the Twilio dashboard.
Put them into `twilio.env` and execute `source twilio.env`

Install dependencies via `pip install -r requirements.txt`

## CSV format

```
Name,PhoneNumber,CoupleId,Language
Buffalo,+456123789,1,en
Mortimer,+123789456,2,en
Wilson,+123456789,3,en
```

## How to run

Execute tests via `pytest`.

Do a dry run: `python send_secret_santas.py <your file>.csv -d`

Send a test message to everyone: `python send_secret_santas.py <your file>.csv -t`

Do the real thing: `python send_secret_santas.py <your file>.csv`
