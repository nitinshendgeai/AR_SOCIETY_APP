# Security Policy

## Secrets

Never commit real credentials, database URLs, API keys, JWT signing keys, passwords, or private keys.

Use `.env` files and deployment-provider secret variables for runtime values. Repository templates must contain placeholders only.

If a credential is ever committed:

1. Rotate/revoke the credential immediately in the provider where it is used.
2. Remove the credential from the repository working tree.
3. Remove the credential from Git history using an approved history-rewrite procedure when required.
4. Force redeployment with the replacement credential.
5. Verify that the old credential no longer authenticates.
6. Review access logs for unauthorized use.

## Reporting

Do not open a public issue containing a secret. Report suspected credentials privately to the repository owner or through GitHub's private security reporting mechanism.

## Pull request requirement

Changes containing runtime credentials must not be merged. Secret scanning should pass before security-sensitive changes are merged.
