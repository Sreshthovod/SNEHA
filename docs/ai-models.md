# AI models, providers and fallbacks

## Principles (enforced in code and tests)

1. **Everything essential works without AI and without the internet**: activities, approved
   memories, routines, personalization and the offline conversation helper.
2. **No diagnostic model, ever.** Nothing classifies, stages or predicts dementia. Analytics
   and recommendations are descriptive engagement rules with disclaimers.
3. **No fake output.** A missing model, unsupported language or unusable audio is reported
   as such (`model_missing`, `language_unsupported`, `invalid_audio`). Transcripts and
   audio are never fabricated.
4. **No automatic weight downloads.** `scripts/download_models.py` is the only path, and it
   writes to the git-ignored `/models` with a manifest (revision and checksums).
5. **Consent gates cloud and voice.** Gemini only with current `cloud_ai` consent;
   transcription only with `voice_processing` consent.
6. **Private text stays private.** Conversation text and transcripts are processed in
   memory, never stored and never logged (tests assert this). Only `conversation_records`
   metadata is kept.

## Summary

| Capability | Provider(s) | Fallback | Runs | Status |
|---|---|---|---|---|
| Activity selection and difficulty | Deterministic rules engine ([spec](../packages/shared_docs/personalization-rules.md)) | n/a | Server **and** phone (Dart port, parity-tested) | ✅ |
| Memory retrieval | Tag, entity and relationship matching over **approved** memories | n/a | Server; phone uses its synced approved cache | ✅ (embeddings: optional future) |
| Conversation understanding | Gemini (optional) → local LLM (optional) → **deterministic** | Deterministic, always | Server; phone has an offline helper | ✅ |
| Speech recognition | faster-whisper (Whisper, CTranslate2) | Touch input | Server | ✅ verified with a real model |
| Speech synthesis | Phone system TTS; server Indic Parler-TTS (optional) | On-screen text | Phone / server | Phone ✅ · server: integrated, not run here |

## Conversation (`services/api/app/conversation/`)

**Chain:**
1. Gemini, if `SNEHA_GEMINI_API_KEY` is set and the patient's `cloud_ai` consent is
   granted.
2. Local OpenAI-compatible model, if `SNEHA_LOCAL_LLM_BASE_URL` is set.
3. Deterministic keyword engine. It always works and makes no network calls.

Any failure falls back to the deterministic engine with a reason code:
`not_configured`, `cloud_ai_consent_not_granted`, `timeout`, `network_unavailable`,
`invalid_credentials`, `quota_exhausted`, `safety_blocked`, `malformed_output`,
`schema_invalid_output`, `empty_output`, `provider_error`.

**Gemini integration** (google-genai 2.31.0, verified against the installed SDK):
- `client.models.generate_content` with `response_mime_type="application/json"`,
  `response_json_schema=<strict Pydantic schema>`, `temperature=0`.
- `HttpOptions(timeout=…, retry_options=HttpRetryOptions(attempts=1))`, so there are no
  retries while the patient waits.
- The model is `SNEHA_GEMINI_MODEL`, default `gemini-3.6-flash` (listed as GA in Google's
  July 2026 release notes). Confirm with `client.models.list()` before deploying.

**Guards** (`guard.py`, applied to every provider's output):
- Mentions must be the person's own words.
- Memory and routine IDs are resolved against **this patient's approved** data; anything
  else is dropped.
- Relationship words count as facts only if both said and stored; otherwise they are
  marked uncertain.
- Memory candidates are returned with `requires_approval: true` and never saved.
- Diagnostic or decline wording is filtered out.
- Distress, fatigue and stop flags are OR-ed with the deterministic detector, so a model
  cannot hide them.
- The patient-facing reply comes only from server templates plus stored titles, never from
  model text.
- Activity suggestions come only from the personalization engine.

**Local LLM:** off by default. A 3–8B instruct model (e.g. via llama.cpp or Ollama) needs
roughly 4–8 GB RAM and benefits from a GPU. Only enable it on hardware where latency is
acceptable.

Hindi, Assamese and Bengali keyword lists and reply templates are **drafts that need
native-speaker review**.

## Speech (`services/api/app/speech/`)

**Recognition: faster-whisper 1.2.1** (MIT; Whisper weights MIT).
- Language coverage was checked against the library's own language table, not
  documentation:
  - **supported:** Assamese `as`, Bengali `bn`, English `en`, Hindi `hi`, Nepali `ne`
  - **not supported:** Bodo `brx`, Garo `grt`, Khasi `kha`, Mizo `lus`, Manipuri `mni`,
    Nagamese `nag`. These get `422 language_unsupported`, and the app keeps touch input.
- Verified end to end in this repository: the `tiny` model transcribed a synthetic
  macOS-`say` recording exactly ("Good morning. I would like a cup of tea.", confidence
  0.71) on CPU (`tests/test_speech.py`).
- Assamese and Nepali accuracy in Whisper is far lower than for English or Hindi; evaluate
  with native, older speakers before relying on it.
- Hardware (measured, Apple M4 CPU, int8): `tiny` transcribes the 2.6 s clip in 0.48 s cold
  (including model load) and 0.13 s warm.
  `small` (≈480 MB) and `medium` (≈1.5 GB) are recommended for real use but have **not been
  benchmarked** on this machine; measure latency on the target server before choosing.
- Input: 16-bit PCM WAV, mono or stereo, 8–48 kHz, 0.3–60 s, resampled to 16 kHz. Silent,
  corrupt and other formats get `422 invalid_audio`.

**Synthesis: AI4Bharat Indic Parler-TTS** (Apache-2.0, gated on Hugging Face).
- The model card lists `as`, `bn`, `brx`, `en`, `hi`, `mni`, `ne` among SNEHA's
  languages; `grt`, `kha`, `lus` and `nag` are not covered.
- It needs PyTorch and `parler-tts` (not installed by default, several GB) and ideally a
  GPU.
- The provider is integrated with lazy loading and honest errors, but **has not been run
  with real weights on this machine**.
- On the phone, read-aloud uses Android's system TTS and checks voice availability per
  language. Without a voice, text stays on screen.

**Candidates evaluated but not integrated:**
- AI4Bharat IndicConformer: MIT, covers the 22 scheduled languages including Bodo and
  Manipuri. It needs AI4Bharat's NeMo toolkit; integrate it when Bodo/Manipuri ASR is a
  priority.
- Meta MMS: very broad coverage, but some checkpoints are non-commercial (CC-BY-NC).

**Setup:**
```bash
cd services/api
uv run python scripts/download_models.py asr --size small   # prints SNEHA_ASR_MODEL_PATH=…
uv run python scripts/download_models.py tts                # gated; `hf auth login` first
```

## Supported language codes

`as` Assamese · `bn` Bengali · `brx` Bodo · `en` English · `grt` Garo · `hi` Hindi ·
`kha` Khasi · `mni` Manipuri (Meitei) · `lus` Mizo · `nag` Nagamese · `ne` Nepali.
`GET /api/v1/speech/status` reports per-language voice support at runtime.
