# EAS Mail Reader

Minimal Exchange ActiveSync client for listing mail folders and syncing message summaries.

## Install

```bash
pip install -e .
```

## Configuration

Set environment variables:

```bash
export EAS_SERVER="mail.example.com"
export EAS_USERNAME="user@example.com"
export EAS_PASSWORD="your-password"
```

Or pass `--server`, `--username`, `--password` flags to each command.

## Usage

### List folders

```bash
eas-mail-reader folders
eas-mail-reader folders --json
```

### Sync messages

```bash
eas-mail-reader messages --collection-id <folder-id>
eas-mail-reader messages --collection-id <folder-id> --json
```

## Project Structure

```
src/eas_reader/
├── __init__.py
├── cli.py          # CLI entry point (folders + messages)
├── config.py       # ClientConfig dataclass
├── transport.py    # HTTP transport with Basic auth
├── wbxml/          # WBXML decoder
│   ├── __init__.py
│   ├── codepages.py
│   ├── decoder.py
│   ├── models.py
│   └── reader.py
└── eas/            # EAS protocol helpers
    ├── __init__.py
    ├── commands.py  # Build WBXML requests
    ├── encoder.py   # WBXML encoder
    ├── models.py    # Data models
    └── parsers.py   # Parse WBXML responses
```
