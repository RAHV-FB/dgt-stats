# Scripts

Planned command-line entry points:

- download or register official source files;
- ingest and validate each source family;
- build processed analytical tables;
- reproduce figures, tables and reports.

Scripts should be thin orchestration layers. Reusable logic belongs in `src/dgt_stats/` and must be covered by tests.
