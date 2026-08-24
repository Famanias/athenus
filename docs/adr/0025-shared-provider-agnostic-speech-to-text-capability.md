# Shared provider-agnostic speech-to-text capability

Athenus routes both uploaded-media transcription and note-recording transcription through the speech-to-text capability selected by the process-wide AI service bus. We rejected constructing a note-specific Faster Whisper adapter because that bypassed provider/model configuration, duplicated lifecycle policy, and allowed the two transcript paths to behave differently. Both paths share capability selection while retaining separate media identities and persistence workflows.

## Consequences

- Changing the active speech-to-text provider applies consistently to videos, audio, and note recordings.
- Feature code must request the speech-to-text capability; only composition and infrastructure code may construct provider adapters.
- Failure is reported from the configured capability rather than silently falling back to a different provider.
