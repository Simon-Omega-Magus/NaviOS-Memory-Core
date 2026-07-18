---
tags: [safety, local-first]
---
# Safety Constraints

Source memory and recovery state remain local; the default engine does not call a remote embedding or model API.

Files whose names suggest tokens, credentials, private keys, environments, or secrets are excluded before indexing.

Retrieval preserves the authority of its source but never creates execution
permission. Stable human directions remain influential until completed,
expired, revoked, or clearly superseded, while consequential work must still
verify exact source handles and current action authority.
