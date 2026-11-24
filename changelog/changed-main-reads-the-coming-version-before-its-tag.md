- Core's `main` reads `version = "0.5.0"` before its tag, so a package pinned to a commit of
  `main` installs within its `~=0.5.0` bound. The release's pull request raises no version: it
  writes the release's heading into `CHANGELOG.md`, and its merge tags `v0.5.0`.
  (https://github.com/xippios/sdk-core/issues/561, https://github.com/xippios/sdk-core/issues/566)
