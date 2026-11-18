- Both adapters keep the metadata of an `Annotated` task parameter: a `Field` constraint,
  a description or a validator reaches the tool's input schema and argument check and the
  route's parameters, where it was dropped and enforced by nobody. A tool answers a value
  that the constraint refuses as any refused argument, and a route as 422.
  (ADR-0007, ADR-0014, §8, §9, https://github.com/xippios/sdk-core/issues/68)
