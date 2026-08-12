# ADR 0004: Versioned IndexTTS-2.5 Runtime Adapter

## Status

Accepted

## Date

2026-08-12

## Context

Dubbing-room currently integrates IndexTTS 2.0 through a project-local source snapshot, an isolated runtime, a Python worker subprocess, and the stable application backend id `indextts2`. The source snapshot has no upstream commit manifest. Runtime readiness is inferred from a 2.0-specific checkpoint list.

IndexTTS-2.5 changes the imported module, tokenizer, codec asset, half-precision option, language contract, speed control, text-emotion loading behavior, and checkpoint inventory. Upstream has no 2.5 Git tag or matching Python package version, so neither the package version nor an unpinned `main` can identify a compatible runtime.

The existing database, API, History, Voice Library, and jobs/takes use `indextts2` as a backend identity. Renaming that identifier would create a data migration with no product benefit. At the same time, continuing to write every generation as model `IndexTTS2` would make old 2.0 and new 2.5 results indistinguishable.

The current multi-take implementation starts one subprocess and loads the model for each take. It is simple and isolated but may make 2.5 multi-take generation unacceptably slow. There is not yet a measured local baseline that justifies a more complex persistent worker protocol.

## Proposed Decision

Adopt a versioned adapter while preserving the stable backend identity.

- Keep `backend_id = "indextts2"` for API, storage, queue, runtime coordination, and historical compatibility.
- Record `model_id = "IndexTTS-2.5"`, `model_version = "2.5"`, and the pinned upstream commit on new jobs, takes, generations, and runtime status.
- Import `indextts.infer_v2_5.IndexTTS2` directly from the application worker. Do not route 2.5 through the upstream `indextts2` console entry, because that entry still targets 2.0.
- Keep source, runtime caches, environments, and checkpoints project-local.
- Give 2.5 a separate checkpoint directory during migration. Never overlay it on the current 2.0 assets.
- Add a source manifest and asset-family detector. Refuse 2.0 source with 2.5 weights, 2.5 source with 2.0 weights, missing commit metadata, and unsupported configuration versions.
- Expose effective capabilities such as supported languages, BF16 availability, text-emotion availability, duration-factor support, and active model version through runtime status.
- Keep the current discriminated emotion modes and stable Voice Library/media contracts.
- Treat the current per-take subprocess lifecycle as the first compatibility implementation only. Benchmark one-take and three-take cold-load behavior before deciding whether to accept it or replace it with one persistent versioned worker per queued job.
- Do not adopt upstream vLLM, TensorRT, or Python-generator streaming as part of this replacement. Each requires a separate decision and acceptance contract.

This ADR remains Proposed until the migration plan's contract tests and cold-load benchmark are reviewed.

## Alternatives Considered

### Rename the backend to `indextts25`

Rejected. It would fragment runtime coordination, stored jobs, filters, and History even though 2.5 is the next implementation of the same product backend.

### Replace files in the current checkpoint directory in place

Rejected. The 2.0 and 2.5 tokenizer and codec inventories are incompatible. An interrupted copy or rollback would leave an ambiguous mixed asset set.

### Identify 2.5 by `indextts` package version

Rejected. The official 2.5 source still reports package version `2.0.0`.

### Move directly to a permanent resident service

Deferred. It could reduce repeated load cost, but it introduces lifecycle, cancellation, crash recovery, structured logging, model unload, and cross-process locking work before a local benchmark demonstrates the need.

### Use the upstream console CLI

Rejected. The installed `indextts2` entry still imports `infer_v2` and checks IndexTTS-2 assets.

## Consequences

- Old records remain readable and continue to use the same backend filters.
- New records become attributable to an exact model family and upstream source revision.
- Runtime status and validation become stricter but provide actionable mismatch errors before expensive model loading.
- A temporary second checkpoint set is required until real-model 2.5 acceptance and rollback review are complete.
- The frontend must use capability data rather than assuming every 2.5 feature is loaded.
- The worker-lifecycle choice remains an explicit checkpoint rather than an accidental refactor.

## Validation Required Before Acceptance

- Contract tests prove correct 2.5 constructor and `infer` mapping.
- Asset tests reject both directions of 2.0/2.5 mismatch.
- Existing 2.0 History, Voice Library, job, and take fixtures remain readable.
- A real one-take and three-take benchmark records load time, synthesis time, peak VRAM, and failure recovery.
- The team chooses per-take subprocess or persistent-per-job worker using the recorded evidence.
- License and distribution implications receive human review.
