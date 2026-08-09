# Nine-stage OrbStack local acceptance — frozen failure 2026-08-09

## Frozen candidate

- Backend: `0228f495b7708b92cc7526f201687eb5b1441565`
- Frontend: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- Guest: `munbon-control-plan-local` (Debian 12 arm64)

## Acceptance-truthful outcome

The sequential run completed seven stages. `LOCAL-WRITE-UI-1` failed at
`write_browser_result_not_accepted` after the browser drill completed, and
`LOCAL-PERSIST-ONLY-1` was not reached. This is `7/9 PASS`, not `8/9`.

Scheduler restoration succeeded on its first attempt. The post-failure snapshot
recorded all four backend services online and ready, the backend write flag
false, and no listener on `127.0.0.1:9999`. See `FINAL-STATE.txt`.

## Preservation notes

`guest-evidence/` is a verbatim copy of the live guest evidence directory made
before any rebuild or diagnostic run. The harness-owned
`guest-evidence/SHA256SUMS` verifies completed PASS manifests and stage state,
but the harness did not index the failure manifest or armed-frontend log.
`guest-evidence-SHA256SUMS` closes that preservation gap by hashing every copied
guest artifact, including `LOCAL-WRITE-UI-1-failure.json`.

The rejected browser result JSON was not retained by the frozen harness, so this
archive cannot prove which validator predicate or predicates disagreed. It does
not claim that one field failed.

The earlier `2026-08-09-nine-stage-orbstack-32d89099` archive is separate and
unchanged.
