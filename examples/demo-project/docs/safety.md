---
tags: [safety, local-first]
---
# Safety Constraints

Source memory and recovery state remain local; the default engine does not call a remote embedding or model API.

Files whose names suggest tokens, credentials, private keys, environments, or secrets are excluded before indexing.

Retrieved cells are evidence rather than execution authority, and consequential work must verify their exact source handles.
