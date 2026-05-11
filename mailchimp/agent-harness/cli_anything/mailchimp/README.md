# cli-anything-mailchimp

Python CLI harness for the [Mailchimp Marketing API v3.0](https://mailchimp.com/developer/marketing/docs/fundamentals/), built on the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) framework.

## Install

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=mailchimp/agent-harness
```

## Auth

```bash
export MAILCHIMP_API_KEY=<your-api-key>-<datacenter>
```

## Usage

```bash
cli-anything-mailchimp ping
cli-anything-mailchimp lists list --json
cli-anything-mailchimp campaigns list --count 10 --json
cli-anything-mailchimp                  # interactive REPL
```

See `SKILL.md` for full command reference.
