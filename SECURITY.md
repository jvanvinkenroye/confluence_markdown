# Security Policy

> **Note:** This project is a proof of concept. No guarantee of correctness or security is provided.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

Please **do not** report security vulnerabilities as a public GitHub issue.

Instead, send an email to: **jan.vanvinkenroye@tik.uni-stuttgart.de**

Include the following information:

- Description of the vulnerability
- Steps to reproduce
- Potential impact

You can expect a response within 7 business days.

## Secure Usage Notes

- Tokens and passwords are stored in the system keychain, not as plaintext
- The config file `~/.config/confluence-markdown/config.json` has permissions `600`
- Avoid passing credentials as shell arguments when other users can read `ps` output — use `--config` instead
