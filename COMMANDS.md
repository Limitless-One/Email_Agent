# NovaGear Email Agent — Command Reference

Run every command below from this project directory:

```sh
cd "/Users/harsha/Desktop/Projects/Email Agent"
```

## Offline testing (no Gmail connection)

| Command | Purpose |
| --- | --- |
| `python3 -m pytest` | Runs the automated unit and integration tests. It does not connect to Gmail. |
| `python3 -m email_agent evaluate` | Replays the built-in 60-case offline evaluation suite. It does not connect to Gmail or send email. |
| `python3 -m email_agent replay examples/replay-input.json` | Runs editable messages from a JSON file and prints the full trace, final response, and simulated send operations. It does not connect to Gmail, send external mail, or write to the NovaGear database. |

### Replay input JSON

Edit [`examples/replay-input.json`](examples/replay-input.json), then run the replay command above. Each message requires `sender`, `subject`, and `text`. `message_id` and `thread_id` are optional, but should be unique per message; reuse a `thread_id` to simulate a conversation.

```json
{
  "messages": [
    {
      "message_id": "my-test-1",
      "thread_id": "my-thread-1",
      "sender": "someone@example.com",
      "subject": "A question",
      "text": "When will my order arrive?"
    }
  ]
}
```

## Live Gmail worker

These commands construct the Gmail client. They require the Gmail configuration in `.env` and can read from the `AI_PROCESS` label.

| Command | Purpose |
| --- | --- |
| `python3 -m email_agent once` | Runs one Gmail polling pass, then exits. With `EMAIL_AGENT_SEND_ENABLED=false`, it plans replies but does not create drafts, send mail, or mark messages complete. |
| `python3 -m email_agent poll` | Runs Gmail polling repeatedly. The delay is controlled by `EMAIL_AGENT_POLL_SECONDS` (90 seconds by default). |
| `python3 -m email_agent export` | Prints operator metrics and tracked-message status from `agent_state.db`. It does not call Gmail. |
| `python3 -m email_agent inspect GMAIL_MESSAGE_ID` | Prints the recorded process and planned reply for one prior message. It does not call Gmail. |
| `python3 -m email_agent debug GMAIL_MESSAGE_ID` | Exports the saved trace for a prior message to `debug/GMAIL_MESSAGE_ID.json`. It does not call Gmail. |
| `python3 -m email_agent retry GMAIL_MESSAGE_ID` | Requeues a `needs_review` or `ready_to_send` message. Run `once` or `poll` afterwards to process it. |

`EMAIL_AGENT_SEND_ENABLED=false` is the safe default. Setting it to `true` allows the live worker to create a Gmail draft, send it, and mark the original message complete.

## Background worker controller

| Command | Purpose |
| --- | --- |
| `./scripts/email-agent start` | Starts `python3 -m email_agent poll` in the background. |
| `./scripts/email-agent status` | Reports whether the background worker is running. |
| `./scripts/email-agent logs` | Shows the latest 100 lines of `run/email-agent.log`. |
| `./scripts/email-agent logs 250` | Shows the latest 250 log lines. |
| `./scripts/email-agent stop` | Stops the background worker. |

The controller writes its PID to `run/email-agent.pid` and its log to `run/email-agent.log`. It persists after the terminal closes, but does not automatically restart after a reboot.

## Sample-data reset

| Command | Purpose |
| --- | --- |
| `python3 database/seed_data.py` | Rebuilds the local sample database and JSON fixtures. **This replaces the contents of `database/novagear.db`; do not use it with operational data.** |

## Help

```sh
python3 -m email_agent --help
```
