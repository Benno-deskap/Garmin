# Security Policy

## About This Project

This is a personal project for processing and serving Garmin fitness data via a local Python server (`server.py`). It is not intended for public deployment or multi-user environments.

## Supported Versions

Only the latest version on the `main` branch is actively maintained.

| Version        | Supported          |
| -------------- | ------------------ |
| main (latest)  | :white_check_mark: |
| older commits  | :x:                |

## Security Considerations

Since this project runs locally and processes personal Garmin data, please be aware of the following:

- **Local use only** — `server.py` is designed to run on your local machine and should not be exposed to the public internet.
- **Garmin data privacy** — `Garmin_clean.json` may contain personal health and activity data. Do not commit sensitive raw exports to a public repository.
- **No authentication** — The server does not implement authentication by default. Do not run it on a shared network without additional safeguards.

## Reporting a Vulnerability

This is a personal/private project, but if you spot a security issue:

1. **Do not open a public issue** for security vulnerabilities.
2. Contact the repository owner directly via GitHub: [@Benno-deskap](https://github.com/Benno-deskap)
3. Describe the issue clearly, including steps to reproduce if applicable.

You can expect a response within a few days. If the vulnerability is valid, it will be addressed in the next commit to `main`.
