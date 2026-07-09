# ADR 0003: Hide promoted generation records from normal History

## Status

Accepted

## Date

2026-07-06

## Context

The desktop AppShell has four production modules that create audio:

- Voice Design
- Voice Cloning
- Ultimate Cloning
- IndexTTS2 Studio

All generated audio is useful as History, but successful generated audio can also become reusable voice material in the Voice Library. Users need to delete ordinary history safely without accidentally deleting audio that has already been saved as a voice.

Before this decision, saving generated audio as a voice copied the audio into `data/app/voices/`, but the source generation remained visible in normal History. That made the same audio appear in two places and made bulk deletion workflows ambiguous.

## Decision

When a generation is saved as a voice, create an explicit relationship between the two records and hide the generation from normal History.

The implementation uses:

- `voices.source_generation_id`
- `generations.saved_voice_id`
- `generations.promoted_to_voice_at`
- `generations.hidden_from_history_at`

Normal History filters out records with `hidden_from_history_at`. Trash uses `deleted_at`, so promoted records are not treated as deleted and do not appear in Trash by default.

The operation is exposed as `promote-generation-to-voice`, which:

1. Validates that the generation exists, is not deleted, and has output audio.
2. Copies the generation output into `data/app/voices/`.
3. Creates the voice row with `source_generation_id`.
4. Updates the generation with the promotion and hidden-history fields.

## Alternatives Considered

### Leave promoted generations visible in History

This keeps the model simple, but it duplicates the same useful audio in History and Voice Library. It also lets users accidentally trash or purge the original history row while believing they are only cleaning disposable results.

### Move promoted generations to Trash

This hides the record from normal History, but it falsely represents a saved voice as deleted. It also puts protected source material into the same bulk-delete surface as disposable failures.

### Reuse the same audio file for generation and voice

This avoids copying files, but it requires shared asset ownership, reference counting, and stricter deletion rules. The current storage model is safer: voice audio is copied into `data/app/voices/`, so History purge cannot remove Voice Library audio.

## Consequences

- History and Voice Library are now intentionally different views of related records.
- Promoted generation records remain traceable for debugging and future migrations.
- Permanent purge remains simple because it only applies to trashed generation rows.
- Future asset deduplication must preserve the invariant that deleting History never deletes audio still owned by a voice.
