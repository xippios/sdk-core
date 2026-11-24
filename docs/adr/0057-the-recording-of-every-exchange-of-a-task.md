# ADR-0057: The recording of every exchange of a task

Status: Superseded by ADR-0066 · Date: 2026-11-22 · Decided by https://github.com/xippios/sdk-core/issues/376 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/455

## Context

`record` and `record_sync` record one exchange each (ADR-0048). A task that makes several calls,
such as sdk-google-mail's `search_messages`, which lists messages and then reads each one, is
recorded by a capture of the source's own: its `scripts/record_fixture.py` builds the demo
account's client for one attempt, chains a hook behind the quota policy's `observe` that keeps
every answer, seeds the client into the registry and guards the seed, runs the task, builds every
fixture with `fixture_from_response` and writes them once all pass, as `<case>.json`,
`<case>_2.json` and so on under the task's name. Conventions §10 places a fixture recorded through
a task under the task's name and states no numbering; sdk-google-mail's docstring does.

sdk-google-mail records its ten recorded tasks this way. sdk-cashctrl records exchange by exchange,
its 44 fixture directories named after wrappers, and sdk-x's seven tasks make one call each, so
neither records through a task today. ADR-0023, decision 2, admits code with two consumers, and
decision 3 admits it with one only for a reason of three kinds, none of which is a recorder of
tasks, so https://github.com/xippios/sdk-core/issues/174 waited for a second consumer by its
decision 4. The maintainer's answer on https://github.com/xippios/sdk-core/issues/364, part 3,
against its recommendation, let the recording of every exchange of a task ride with the recorder's
frame of 0.4.1, and https://github.com/xippios/sdk-core/issues/376 decided its shape.

The sources reach their clients in two ways: the tasks of sdk-google-mail and sdk-cashctrl fetch
theirs from a `Tenants` registry, and sdk-x's wrappers bind a module-level client by name. A
recorder that builds its own client reaches the first two only by seeding the registry, and sdk-x
not at all, and ADR-0048, decision 3, removes the client built for one attempt.

## Decision

1. **The helper enters core with one consumer, by the maintainer's answer.** `record_task` enters
   with one source that records through tasks, sdk-google-mail. Its reason is the answer on
   https://github.com/xippios/sdk-core/issues/364, part 3: the recording of every exchange of a
   task rides with the recorder's frame. It is none of the reasons of ADR-0023, decision 3, and
   ADR-0023 stands as written: its decisions 2 and 3 judge the next helper as before.
2. **A collector inside core's client.** While a task is recorded, every `AsyncClient` of the
   running context hands each answer it read whole to a collector, in the order the answers
   arrived. It sends each request once, whatever its `RetryPolicy` says, and neither reads nor
   fills the response cache, as `send_once` does (ADR-0048, decision 3); its `before_request`, its
   limiter and its `observe` run as for any request. The collector is private to
   `xippios.core.client` and held in a context variable, the context of the running task, which
   a task it starts inherits: two recordings at once never mix, a request of another task is never
   collected, and a task that outlives the recording hands it nothing. Off, the client sends,
   retries and caches as before. A task whose requests run at once is collected in the order its
   answers arrived, which may change from one recording to the next.
3. **What the collector does not see.** httpx sends a token request that runs inside an auth flow
   before the request it signs, and answers inside the flow the 401 after which a renewing bearer
   sends a request again: the collector sees each request's final answer alone, and the token
   exchange keeps a fixture of its own (§10). A download's success streams its body to a file
   unread, so no fixture of the task can keep it: a download while a task is recorded is refused
   before it is sent, and the recording with it, the message naming the exchange's number and the
   request. A gap would leave fixtures that replay no whole run of the task, where
   https://github.com/xippios/sdk-core/issues/376 records every exchange that a task makes.
4. **The entry point.** `record_task(task, *args, fixtures, case, scrub=None, rewrite=None,
   **kwargs)` and `record_task_sync` await the task as the MCP adapter awaits it, a sync facade
   through its async twin. `task` is positional only, so a keyword of the task named `task`
   reaches the task. A task that takes `fixtures`, `case`, `scrub` or `rewrite` by keyword is
   refused with `TypeError` before it runs, the message naming the clash, since the helper takes
   those names as its own and would hide the task's.
5. **Each exchange passes the frame, and all or none is written.** Each answer passes the refusal
   of a 1xx or a 3xx, the scrub, the rewrite step and the check of ADR-0048, decisions 1, 2 and 4,
   through `fixture_from_response`, and its text is built in memory with `fixture_text`, before
   the first write. A refusal of any exchange raises, the message naming the exchange's number,
   the file it would have been written to and the place within the fixture, never a value, and no
   file is written. A task that raises writes nothing, and neither does a task that sends no
   request. The task's error is raised as it came, unless an answer of a 1xx or a 3xx or a
   download came before it: the recording then raises the frame's refusal of the first of them,
   the exchange's number and its status or request named, with the task's error as its cause,
   since the recorder refuses such an answer on every path, whatever the task made of it
   (ADR-0048, decision 4). The exchanges are judged in the order they were made. Every request of
   the task was sent by the time a refusal comes, so a write among them may have been applied,
   and the message says so once.
6. **Numbering and place.** The fixtures stand under the task's name without `_async`, the first
   at `fixture_path(fixtures, <task>, case)` and the k-th, from the second on, at
   `<case>_<k>.json`. Where a numbered file of the case stands beyond the last exchange, as when a
   task is recorded again with fewer exchanges, the recording is refused before anything is
   written, the message naming each such file. The recorder deletes no fixture: §10 makes the
   deletion of a fixture that no test replays the PR's, named in its description (ADR-0039,
   decision 8), and a case whose own name ends in `_<k>`, such as §10's `CH_2026_8`, may stand
   beside the case `CH_2026`.
7. **The replay stays as it is.** `replay_fixture` mounts one fixture per route on its method, host
   and path (§10), so a task's fixtures replay where its calls differ by path or by the parameters
   a test names with `match_params`. Two exchanges on one path that no parameter tells apart share
   one route, the later answer replacing the earlier, and no replay in order enters core with this
   record.

## Consequences

- sdk-google-mail deletes its own capture in its patch: the client it builds for a task's
  recording, the seed of the registry and its guard, and the loop that numbers, builds and writes
  the fixtures. It records with `record_task_sync` and keeps its command line, the write safety
  rule, `MessageScrub`, its rewrite rules and `check`, run as its step. The changelog's Hand-apply
  note names what goes and what stays.
- sdk-cashctrl and sdk-x take nothing now: sdk-cashctrl records exchange by exchange under the
  names of its wrappers, and three of its tasks download, and sdk-x's tasks make one call each.
- A task that downloads is recorded exchange by exchange, its download with its sample (ADR-0020,
  decision 6), and a task's error answer is recorded as one exchange, as before.
- `max_read_bytes` bounds no answer of a task: its answers are read as its client reads them.

Conventions §10, the README and the docstrings of `record_task` and `xippios.core.testing` state
its decisions from 1.29 on.

## Amendment 2026-11-22

https://github.com/xippios/sdk-core/issues/455 amends decision 1, from finding 1 of the
organization's range review of core 0.4.1
(https://github.com/xippios/sdk-core/pull/453#issuecomment-7082327015). `record_task` and
`record_task_sync` enter core with one consumer, sdk-google-mail, by reason (d), which ADR-0058,
decision 1, adds to the three of ADR-0023, decision 3. The decision that admitted them is the
maintainer's answer on https://github.com/xippios/sdk-core/issues/364, part 3, the design
question of step 17, that the recording of every exchange of a task rides with the recorder's
frame of 0.4.1, which step 17's follow-up, 17.1, built. His answer on
https://github.com/xippios/sdk-core/issues/376, the design question of step 17.1, decided the
helper's shape and not its entry. Decision 1's words that
the helper's reason is none of the reasons of ADR-0023, decision 3, stay true of its three, and
its words that ADR-0023 stands as written read from this amendment: ADR-0023 stands but for the
fourth reason of its decision 3, and its decisions 2 and 3 judge the next helper as before.
Decisions 2 to 7 stand as written.
