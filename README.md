# NovaGear Email Agent

This prototype is a single Python support-email worker built on the existing `rag/` and `database/` packages. It reads only messages manually labeled `AI_PROCESS`, uses plain-text email parts only, validates model output, and stores an audit trail in a separate SQLite database.

## Safety model

- The worker never searches every unread inbox message and never processes attachments or HTML.
- `EMAIL_AGENT_SEND_ENABLED` defaults to `false`. Set it to `true` only after the offline suite and a Gmail sandbox pass.
- The agent can retrieve customer/order facts and create internal support tickets; it cannot change orders, issue refunds, or create RMAs.
- OAuth paths and model keys come only from environment variables. Do not reuse the notebook's Downloads paths or commit tokens.

## Run locally

1. Copy `.env.example` to a new `.env` file and replace each placeholder with your real value, or export the variables in the same shell that runs the worker. `.env` is loaded automatically and is ignored by Git. Create the Gmail `AI_PROCESS` label manually.
2. Run the test suite: `python3 -m pytest` and replay the offline suite: `python3 -m email_agent evaluate`.
3. Run one safe polling pass: `python3 -m email_agent once`.
4. Export the operator ledger: `python3 -m email_agent export`.

For a live provider, set `EMAIL_AGENT_MODEL_PROVIDER` to `gemini` or `openrouter`, plus `EMAIL_AGENT_MODEL` and `EMAIL_AGENT_MODEL_API_KEY`. The default `rule_based` adapter is an offline fixture/development fallback.

## Test without Gmail

`python3 -m pytest` uses an in-memory mail adapter, so it never connects to Gmail and never sends an email. `python3 -m email_agent evaluate` replays 60 versioned support and safety scenarios through another in-memory adapter, with sending disabled. Neither command needs Gmail OAuth credentials or reads from a mailbox.

Use both before a deployment:

```sh
python3 -m pytest
python3 -m email_agent evaluate
```

The evaluation must report `"acceptance_ready": true` before treating it as a release gate. The cases include order cancellation and tracking, returns and warranty, unowned-order privacy, injection attempts, safety hazards, legal/chargeback requests, human handoff, quoted text, and vague requests.

For an editable, single-scenario or multi-message test, copy and edit [`examples/replay-input.json`](examples/replay-input.json), then run:

```sh
python3 -m email_agent replay examples/replay-input.json
```

The command prints the submitted input, every recorded worker event, model debug information, simulated draft/send/complete operations, and the final response plan. It uses a temporary state database, a rule-based local provider, simulated tickets, and an in-memory mail adapter: it does not connect to Gmail, send an external email, or write to the NovaGear database. Include multiple messages with the same `thread_id` to test a conversation; give each a unique `message_id`.

The included database is sample data. To reset it to the checked-in fixture state for test work, run `python3 database/seed_data.py`. This replaces the local `database/novagear.db` contents, so do not run it against any real operational data.

## Run in the background

The project-local controller runs the existing `poll` command in the background and stores its PID and log under `run/`:

```sh
./scripts/email-agent start
./scripts/email-agent status
./scripts/email-agent logs
./scripts/email-agent stop
```

`start` uses the values in `.env`, including `EMAIL_AGENT_POLL_SECONDS` (90 seconds by default). It will make live Gmail calls once the worker polls, and it will create/send replies only when `EMAIL_AGENT_SEND_ENABLED=true`; keep that setting `false` during dry runs. The controller keeps the process alive after the terminal closes, but it is not a reboot-resilient service manager. For always-on production deployment, wrap the same command (`python3 -m email_agent poll`) in your host's service manager (for example, launchd on macOS or systemd on Linux).

## Debugging a reviewed message

`agent_state.db` stores message status, trace IDs, tool/source IDs, drafts, send outcomes, and safe error details. It does not store raw email text or model output by default. For local troubleshooting only, set `EMAIL_AGENT_DEBUG_ARTIFACTS=true`; model JSON responses are then written to the local `debug_artifacts` table. Export one trace to a readable local JSON file with `python3 -m email_agent debug GMAIL_MESSAGE_ID`. After correcting configuration or test data, explicitly requeue a `needs_review` or send-disabled `ready_to_send` message with `python3 -m email_agent retry GMAIL_MESSAGE_ID`, then run `python3 -m email_agent once`.

For a concise terminal view of the exact planned reply and state transitions, run `python3 -m email_agent inspect GMAIL_MESSAGE_ID`.
