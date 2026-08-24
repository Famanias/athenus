# Athenus Learning Context

Athenus turns source material into workspace-isolated, traceable learning resources. This glossary defines the domain language shared by ingestion, learning, and playback experiences.

## Language

**Workspace**:
The ownership boundary that groups source material, transcripts, conversations, and learning artifacts for one body of study.
_Avoid_: Project, collection, tenant

**Media Item**:
A video or audio source selected for ingestion and playback within one workspace.
_Avoid_: File, asset, upload

**Document**:
A page-oriented source whose locations are expressed as page and section provenance rather than playback time.
_Avoid_: Media item, PDF file

**Transcript**:
The complete time-aligned textual representation of one media item's spoken content.
_Avoid_: Captions, notes, raw text

**Transcript Segment**:
A display and navigation unit of a transcript with a start time, end time, and spoken text.
_Avoid_: Subtitle, paragraph

**Transcript Chunk**:
A retrieval unit derived from one or more transcript segments and used as source evidence for learning artifacts and answers.
_Avoid_: Transcript segment, embedding

**Processing Job**:
The observable lifecycle of transforming a source into usable learning material, including progress and failure state.
_Avoid_: Upload, worker, task

**AI Capability**:
A provider-independent kind of AI work, such as speech-to-text, text generation, embeddings, document parsing, or OCR.
_Avoid_: Provider, model, adapter

**Active Provider**:
The configured provider selected to fulfill an AI capability.
_Avoid_: Capability, model

**Note**:
A workspace-owned learning artifact containing user-authored or generated study content, optionally grounded in one media item.
_Avoid_: Transcript, summary, document

**Note Folder**:
A workspace-local organizational container whose deletion also removes the notes it owns.
_Avoid_: Workspace, tag, collection

**Note Section**:
An ordered part of generated note content with optional source provenance.
_Avoid_: Transcript chunk, paragraph

**Learning Artifact**:
A derived study resource, such as a note, flashcard deck, or quiz, created from workspace knowledge.
_Avoid_: Source, transcript, output

**Source Provenance**:
The workspace, source identifier, source units, and location range that support a derived statement or learning artifact.
_Avoid_: Citation text, metadata
