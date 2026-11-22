# ADR-0050: What a write task's preview shows

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/369

## Context

ADR-0036, decision 9, and conventions §8 give the confirm rule: a write task takes `confirm: bool
= False`, a write server refuses one that does not, and a call without `confirm` returns a dry-run
preview. Neither says what the preview shows, nor whether it reads the record it would change
first (https://github.com/xippios/sdk-core/issues/182), and the agent that decides on `confirm`
decides from the preview. The two sources with write servers answer it two ways on 2026-11-21:

- sdk-cashctrl's fourteen write tasks return a `WritePreview`, the form `payload` upstream would
  receive. Eight of them read first, the updates and deletes of journal entries, persons, orders
  and order book entries: an update builds its whole payload from the stored record, since
  upstream treats every parameter an update leaves out as empty, and two deletes refuse an entry
  that only a read shows to be booked elsewhere. The other six read nothing.
- sdk-google-mail's five write tasks return a `ComposePreview` or an `ActionPreview`, read
  nothing, and say so in the module's docstring, but for a reply: its preview reads the original
  message once, 20 quota units, since the headers a reply sends are the original's. A read of the
  message that a modify or a trash would change costs 20 units against 5 for the modify.

Both tag a preview `performed: Literal[False]`, the field that tells it from the confirmed answer.
`assert_write_tools`, in core since 0.4.0 (ADR-0042, decision 1), holds the write server, its
tools and `confirm`, and nothing of the preview; each source asserts by hand that a preview sends
nothing, or one read.

The question offered four answers: a preview shown from the arguments alone, which drops the
eight reads of sdk-cashctrl and the reply's; the record always read first, which adds a read to
three of sdk-google-mail's previews, a `drafts.get` wrapper it lacks and mailbox content in the
preview; a flag `read: bool` in place of a list; and the docstring alone, with no field and no
check. The human chose that the source decides and the preview says so, held by a test.

## Decision

1. **A preview sends no write and shows the action as the confirmed call would send it.** While
   `confirm` is not true, a write task sends no request that changes what upstream holds, and its
   answer is the preview: the operation and what the confirmed call would send, by upstream's
   names, such as sdk-cashctrl's `payload` or sdk-google-mail's headers and first lines. This
   record builds on ADR-0036, decision 9, and changes nothing of it.
2. **Whether a preview reads first is the tool's.** A preview may read before it shows the
   action, the record an update would change or the message a reply answers, or read nothing.
   The write task's docstring says which, and what the read costs, so the agent that decides on
   `confirm` has the grounds before it calls. A fixed rule either way breaks tools whose read is
   forced or dear: sdk-cashctrl's updates cannot build their payload without the record, and
   sdk-google-mail would pay for a read on every preview.
3. **The preview carries `reads`.** The preview's model declares `reads: list[str]`, the
   operations the preview read, each by its upstream name as `meta.endpoint` names an operation
   (conventions §4), and `[]` when it read nothing. A list names the cost, which a flag does not.
4. **`assert_write_tools` holds the field.** With `preview_reads=True` it fails a write task
   unless its return annotation is a `Result` whose data has exactly one member tagged
   `performed: Literal[False]`, the preview, and that member declares `reads: list[str]`. It
   reads annotations only. It is off by default, so a source that calls it as on core 0.4.0
   passes until its patch on core 0.4.1 declares the field and switches the check on.
5. **The dry run, on request.** With `dry_run=`, the arguments of a call of each write task
   keyed by the task's name, one mapping or a list of them, and `sent=`, the `respx` router the
   test's routes are mounted on, `assert_write_tools` calls each tool of the write server
   without `confirm`, as an agent does, and asserts that the answer is the preview, `performed`
   false, that no request but a read was sent, and that `reads` is empty exactly when no request
   was sent. The dry run holds the field of decision 4 too, since it reads `reads`. It is off by
   default, since it needs the routes that a source's previews read.
6. **A read is a request of a safe method, unless the source says otherwise.** By default a
   request is a read when its method is one of `IDEMPOTENT_METHODS`, `GET`, `HEAD` and `OPTIONS`,
   the methods core's retry rule repeats (ADR-0011, decision 2): sdk-cashctrl reads with `GET`
   and writes with `POST`. `is_read=`, a function of the `httpx.Request`, replaces that rule for a
   source whose upstream reads through `POST`, or whose preview's read sends a token request
   first, as sdk-google-mail's reply does. The dry run sees what was sent through the router's
   calls, as `sent_urls` and `sent_bodies` see a route's, and names a request by its method and
   path, never its host or query (ADR-0030, decision 4).
7. **This record stands beside ADR-0036, decision 9.** The human's answer puts the rule's record
   line at ADR-0036, decision 9. That decision stays one rule, the confirm parameter checked at
   registration and the write server held to loopback, and this record holds what the preview
   shows and its check, so conventions §8 cite both at the preview's sentences.

Two sources consume it, sdk-cashctrl and sdk-google-mail (ADR-0023, decision 3).

## Consequences

- A source's patch on core 0.4.1 declares `reads` on its preview models, sets it in each preview,
  says in each write task's docstring whether its preview reads and what that costs, and passes
  `preview_reads=True`, and `dry_run=` with `sent=` where its tests serve the reads.
- sdk-cashctrl sets the field in one place, its `_preview`, from the read it made; sdk-google-mail
  declares it on two models and sets it in its five previews, a reply's naming
  `gmail.users.messages.get`.
- The check compares a field with the requests sent and reads no prose: what a docstring says of
  a preview's read and its cost stays the review's (review checklist, item 18).
- A request that no route of the test answers fails the dry run's call with `respx`'s own error,
  which names the request, before the check judges it.
