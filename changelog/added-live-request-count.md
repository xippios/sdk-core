- After a run of the live tests, the testing plugin's summary prints the requests that the
  live tests sent, by host, `requests sent by the live run: 15 (api.example.org: 15)`, so a
  release PR reads its count of live calls from the log of each run. A run that built a
  `Tenants` registry names no host, since a tenant's host names the tenant. A run whose live
  tests all skip at their setup prints a count of 0, and a run in which no live test was set
  up with the gate open prints nothing new.
  (ADR-0030, ADR-0035, https://github.com/xippios/sdk-core/issues/335)
