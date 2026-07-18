# Authoritative Checkpoint

## Objective

Finish and verify the compaction-recovery demonstration.

## Current State

The project memory has been indexed and the retrieval query has exact source handles.

## Constraints

Keep source memory local, preserve provenance, and never continue a consequential tool call while post-compaction recovery is pending.

## Next Action

Run the recovery simulation and inspect the frozen bundle before reissuing the intentionally cancelled tool call.
