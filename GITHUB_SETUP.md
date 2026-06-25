# GitHub and HACS publishing checklist

This repository is prepared for:

`https://github.com/bfulham/ae200`

If a different repository name is used, update the `documentation` and
`issue_tracker` URLs in `custom_components/ae200/manifest.json`, plus the
links and badges in `README.md`.

## GitHub repository settings

Set the repository to **Public** and use:

**Description**

> Home Assistant integration for Mitsubishi Electric AE-200 air-conditioning controllers.

**Topics**

- `home-assistant`
- `hacs`
- `mitsubishi-electric`
- `ae200`
- `air-conditioning`
- `climate`
- `home-assistant-custom-component`
- `local-control`

Also:

- Enable **Issues**
- Enable **Discussions** if the README support link will be used
- Allow GitHub Actions to run
- Push the repository's default branch
- Confirm the **Validate** workflow passes

## First release

The integration version is `1.1.0`.

Create and push the matching tag:

```bash
git tag v1.1.0
git push origin v1.1.0
```

The release workflow verifies that the tag matches the unchanged
manifest version and creates a full GitHub release.

## Add as a HACS custom repository

Users can add:

`https://github.com/bfulham/ae200`

as category **Integration** under HACS → Custom repositories.

## Submit to the default HACS catalogue

Before submitting:

- The repository must be public
- HACS validation must pass without ignored checks
- Hassfest must pass
- The repository must have at least one full GitHub release
- Brand assets must remain in `brand/`
- The repository description, topics and Issues must be enabled

Then submit the repository to the integration list in `hacs/default`.
