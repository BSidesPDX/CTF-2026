# MFA solve

Flowchart here: https://excalidraw.com/#json=Eoi9akvbSsyw47XjjH7VB,XaeIzwcKeg2H1JnBF4vA3A

Prompt directs players to `https://tangerineprinting.biz`.

## 1. Player discovers credentials in About Us image

The headshot image for Alice Guererro looks like it has a sticky note on the
monitor, which can be opened in a new tab for full resolution and view the
email and password on it.

## 2. Login attempt

Player tries to log in to the linked 'Employee Login' site `auth.tangerineprinting.biz` with Alice's
credentials but are prompted for a phone extension / call for TOTP code.

## 3. Further investigation

Company site has a 'Submit Design' form, which asks for a "URL of Your Logo
Design" (not a file upload, suspicious!). The backend passes this into PHP
`file_get_contents()` and on error shows the body to the website if it is not a
valid PSD mime type. This can be used for SSRF or local file reads. Player pokes
around using this and either
- discovers there is a Apache `mod_status` site running at the default config of `localhost:80/server-status`; or
- reads in the Apache access logs file /var/log/apache2/access.log

## 4. Voip Admin

Both methods reveal there is a ping bot logging in to
`voipadmin.tangerineprinting.biz` with credentials as query parameters.

Player logs in and is able to see the list of active phones and extensions, and
can 'remote' in to the phone configuration site. That has the ability to record
a PCAP of all traffic coming in to the phone.

## 5. Trigger call

Players now know the extension and can record the call, so:

- start recording on the phone
- log in to the company portal
- input the now-known extension and trigger the phone call
- stop recording after a bit and download pcap
- extract code from the voip call data
- continue login flow

Once logged in, "Alice" can open up the internal email site linked from the
dashboard and get the flag.
