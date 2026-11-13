# Reports

The dated evidence that a decision record of `docs/adr/` or a change cites: what was probed,
measured or found, as it stood on the day.

- **Its name.** `docs/reports/YYYY-MM-DD-<slug>.md`: the day of the finding, then its subject in
  lowercase letters and digits, the words joined by hyphens.
- **Its form.** `# <subject>, YYYY-MM-DD`, then what was found, `## Basis` with what the finding
  rests on, and a section per finding. A commit it cites is a link to that commit.
- **Written once.** A report is not edited after it lands. A later finding is a new report, and a
  record or a change cites a report by its URL.
