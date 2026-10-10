# Release maintenance

Git stores packaging code, patches, tests, documentation, and `SHA256SUMS`.
Root-level release archives are ignored and are attached to GitHub Releases.
GitHub's automatically generated source ZIP/tarball contains repository source;
users must download the named binary assets from the release.

## Current asset set

The current hosted release tag is `untagged-2e0e0fc50c0c16a8970e`. Keep the Linux, Windows, macOS
r1, and macOS r2 archives as separate assets with their original filenames and
bytes. r1 is a checksum-pinned build input for reproducing r2; retain it even
though r2 is the recommended macOS install. The existing package provenance,
licenses, patches, and validation limits remain inside the bundles and under
`macos/`.

## Publish a release

1. Build and validate the packages using `macos/BUILD.md`. Verify each outer
   archive hash against `SHA256SUMS`. Any changed bytes require a new release
   version and updated checksum; never replace an already published asset.
2. Commit the reviewed packaging code, docs, and checksums. The tag must point
   to an archive-free commit. For the initial migration, finish the reviewed
   history cleanup before publishing or locking the release tag.
3. Enable repository immutable releases before publishing. Create a draft
   release at the explicit source commit, upload the archives and `SHA256SUMS`,
   then download all draft assets into a fresh directory and verify them.
4. Publish the verified draft. For later versions, use a new tag and update
   the English and Chinese download tables and the pinned rebuild inputs.

Example commands after the source commit is ready (replace `SOURCE_COMMIT`):

```sh
gh release create debugserver-v5.18.10-r2 --draft --latest=false \
  --target SOURCE_COMMIT --repo Taixin-Semiconductor/XuanTie-DebugServer \
  --title 'XuanTie DebugServer V5.18.10 / macOS r2' --notes-file release-notes.md
gh release upload debugserver-v5.18.10-r2 /path/to/assets/* \
  --repo Taixin-Semiconductor/XuanTie-DebugServer
gh release download debugserver-v5.18.10-r2 --dir /path/to/empty-verification-dir \
  --repo Taixin-Semiconductor/XuanTie-DebugServer
(cd /path/to/empty-verification-dir && shasum -a 256 -c SHA256SUMS)
gh release edit debugserver-v5.18.10-r2 --draft=false --latest \
  --repo Taixin-Semiconductor/XuanTie-DebugServer
```

Do not use `--clobber`, a moving `latest` URL for automated installs, or Git LFS
for these release downloads. Removing an archive in a new commit does not
remove the blob from older Git history. Back up the old history and archives
before any coordinated history replacement; existing clones must migrate to
the rewritten history afterward.
