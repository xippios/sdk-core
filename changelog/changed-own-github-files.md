- `.github/CODEOWNERS` is the repository's own file: its header says so, and it names the
  paths that sdk-template renders for a source, without the lines under `src/` and of
  `workspace.toml`, `composer.json` and `package.json`, which matched no file here. The
  comment of `.github/workflows/publish.yml` names the maintainer who approves the `pypi` run
  by role and says that nobody pushes the tag by hand, and no step of the workflow changes.
  (https://github.com/xippios/sdk-core/issues/224, https://github.com/xippios/sdk-core/issues/215)
