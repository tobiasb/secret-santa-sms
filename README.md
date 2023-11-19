# Elfbot 3000

Takes a list of people from a CSV file and randomly generates secret santa mappings.
Sends text messages (Signal) to everyone. That's it.
Also it supports "groups". People within a group won't get someone within the same group as secret santa.
Also it's anonymous, the organizer won't know who has whom.

_NOTE: Requires Signal CLI REST API_

## Setup

Install dependencies via `pip install -r requirements.txt`

## CSV format

```
Name,PhoneNumber,GroupId,Language
Buffalo,+456123789,1,en
Mortimer,+123789456,2,en
Otto,+237894561,2,en
Wilson,+123456789,3,de
```

In this example, because Mortimer and Otto have the same group ID, they won't get each other as secret santa.

## How to run

Execute tests via `pytest`.

Do a dry run: `python send_secret_santas.py <your file>.csv --signal-cli-api-host=localhost:9000 --from-number=+15555555555 -d`

Send a test message to everyone: `python send_secret_santas.py <your file>.csv --signal-cli-api-host=localhost:9000 --from-number=+15555555555 -t`

Do the real thing: `python send_secret_santas.py <your file>.csv --signal-cli-api-host=localhost:9000 --from-number=+15555555555`
