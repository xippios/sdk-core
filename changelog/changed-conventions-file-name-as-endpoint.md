- Conventions §4 sets a file task's `meta.endpoint` to the file's name as upstream names
  it, `wasde1026.xml` rather than the file kind `wasde.xls`, and a list packaged from a
  released file names that file the same way. A file read from a publisher's own mirror
  is named so too, the URL sent in `meta.request`, and a download of an operation's
  answer keeps the operation's name.
  (ADR-0020, §4, §6, https://github.com/xippios/sdk-core/issues/135,
  https://github.com/xippios/sdk-core/issues/244)
