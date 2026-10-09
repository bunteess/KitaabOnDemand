# Provider documentation

Real adapters are built only from the official documentation kept here
(`docs/INTEGRATIONS.md`). Make one folder per provider, named with the code
used in the settings:

| Folder | Provider | Setting that enables it |
| --- | --- | --- |
| `easypaisa/` | Easypaisa | `PAYMENT_PROVIDERS` |
| `jazzcash/` | JazzCash | `PAYMENT_PROVIDERS` |
| `card/` | The chosen card gateway | `PAYMENT_PROVIDERS` |
| `trax/` | Trax | `COURIER_PROVIDERS` |
| `leopards/` | Leopards Courier | `COURIER_PROVIDERS` |
| `tcs/` | TCS | `COURIER_PROVIDERS` |
| `<sms-code>/` | The chosen SMS gateway | `SMS_PROVIDER` |

In each folder, put:

- the API reference as the provider published it (PDF or saved HTML), or a
  `SOURCE.md` with the URL, version and date you were given;
- notes on the sandbox: base URL, test card or wallet numbers, how webhooks are
  signed;
- nothing secret. Keys, passwords and webhook secrets go in the server
  environment, never in git.
