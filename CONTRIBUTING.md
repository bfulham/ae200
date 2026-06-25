# Contributing

Contributions, controller dumps, testing and documentation improvements
are welcome.

## Before opening a pull request

1. Create an issue describing the change, unless it is a small typo or
   documentation correction.
2. Do not include controller credentials, private addresses or sensitive
   site names in test fixtures.
3. Keep every write command restricted to one explicit AE-200 group.
4. Add or update tests for protocol changes.
5. Run:

   ```bash
   python -B -m unittest -v tests/test_protocol.py tests/test_models.py
   ```

6. Ensure the HACS and Hassfest GitHub Actions pass.

## Controller protocol changes

Prefer evidence from a read-only controller capture over assumptions.
Attach a redacted dump to the related issue and describe the controller
model and firmware.

## Versioning

The integration uses semantic versioning. The version in
`custom_components/ae200/manifest.json` must match the GitHub release tag
without the leading `v`.
