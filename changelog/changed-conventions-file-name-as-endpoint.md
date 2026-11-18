- Conventions §4 sets a file task's `meta.endpoint` to the file's name as upstream names
  it, `wasde1026.xml` rather than the file kind `wasde.xls`, and a list packaged from a
  released file names that file the same way. A download of an operation's answer keeps
  the operation's name, a file whose name carries the dataset's name is named by the part
  that every dataset's file shares, sdk-faostat's `All_Data_(Normalized).csv`, and a file
  read from the publisher's own origin or mirror keeps its name, the mirror's URL in
  `meta.request`.
  (ADR-0020, §4, §6, https://github.com/xippios/sdk-core/issues/135,
  https://github.com/xippios/sdk-core/issues/244,
  https://github.com/xippios/sdk-core/issues/280,
  https://github.com/xippios/sdk-core/issues/276)
