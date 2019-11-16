# Elfbot 3000

Takes a list of people from a CSV file and randomly generates secret santa mappings.
Sends text messages (SMS) to everyone. That's it.
Also it supports couples so people get someone other than their spouse.
Also it's anonymous, the organizer won't know who has whom.

_NOTE: Requires Twilio account_

## Setup

Set up the following environment variables with your information from the Twilio dashboard.

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

## CSV format

```
Name,PhoneNumber,CoupleId
Buffalo,+456123789,1
Mortimer,+123789456,2
Wilson,+123456789,3
```