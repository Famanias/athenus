# Local-First & Offline-First Philosophy

This platform is designed to be **local-first**, **offline-capable**, and **privacy-first**.

A user should be able to run the entire application on their own computer without relying on any external cloud services.

Cloud providers should be treated as optional enhancements rather than mandatory dependencies.

## Core Principles

* The application must work completely offline whenever possible.
* Users own their data.
* Videos, transcripts, embeddings, databases, and generated learning materials remain on the user's machine by default.
* Internet access should only be required when the user explicitly enables cloud providers.
* Every cloud dependency should have a local equivalent whenever practical.
* Cloud services should improve performance, speed, or model quality—not provide essential functionality.

---

# Local-First Architecture

The system should prioritize the following stack:

* Local LLMs via Ollama
* Faster-Whisper for speech recognition
* Local embedding models
* Qdrant running locally via Docker
* PostgreSQL or SQLite for metadata
* Local filesystem or MinIO for storage

The application should function entirely without an internet connection.

---

# Provider Abstraction

Every AI provider must be implemented through an abstraction layer.

Never hardcode OpenAI, Gemini, Claude, Groq, or any specific vendor into the core business logic.

Example:

LLM Provider Interface

↓

OpenRouter Provider

Groq Provider

Gemini Provider

Claude Provider

Ollama Provider

Future providers should be added without modifying application logic.

The same abstraction principle applies to:

* Embedding models
* Speech-to-text
* OCR
* Vision models
* Vector databases
* Object storage

---

# Cloud Augmentation

Cloud services should be optional.

Users may choose to enable:

* OpenRouter
* Groq
* Gemini
* Claude
* Deepgram
* Voyage AI
* Qdrant Cloud

The platform should automatically use these services only when configured by the user.

Otherwise, it should fall back to local providers.

---

# Intelligent Provider Routing

The architecture should support configurable provider routing.

Examples:

Speech-to-text

Preferred:
Faster-Whisper

Fallback:
Deepgram

LLM

Preferred:
Ollama

Fallback:
OpenRouter

Embeddings

Preferred:
BGE or Nomic

Fallback:
Voyage AI

Vector Database

Preferred:
Local Qdrant

Fallback:
Qdrant Cloud

Routing should be configurable through application settings rather than requiring code changes.

---

# Resource-Aware Execution

The platform should automatically adapt to the user's hardware.

Example profiles:

Low-end PC

* CPU inference
* Smaller embedding models
* Lightweight LLMs
* Lower memory usage

Mid-range PC

* GPU acceleration
* Medium embedding models
* Larger local LLMs

High-end Workstation

* Larger local models
* Faster indexing
* Parallel processing
* Multimodal pipelines

Cloud Mode

* Premium cloud models
* Maximum quality
* Faster processing

Users should be able to manually override automatic selections.

---

# Privacy

By default:

* Videos remain local.
* Audio remains local.
* Transcripts remain local.
* Embeddings remain local.
* Vector databases remain local.
* Generated notes remain local.
* Learning history remains local.

If cloud providers are enabled, only the minimum required data should be transmitted.

The system should always make it clear when data leaves the user's device.

---

# Open-Source Friendly

The project should never depend on proprietary APIs for its core functionality.

All essential features must be achievable using open-source software.

Cloud providers should enhance the experience but should never be required to use the platform.

The project should be installable and usable by anyone using only open-source components.

---

# Deployment Philosophy

The application should support three deployment modes:

## Local Mode (Default)

* Runs entirely on the user's machine.
* No internet required.
* Uses local AI models.
* Maximizes privacy.

## Hybrid Mode

* Uses local infrastructure by default.
* Selectively routes specific workloads to cloud providers.
* Balances privacy, speed, and model quality.

## Cloud Mode

* Deployable to cloud infrastructure.
* Uses managed AI services.
* Supports remote access and collaboration.
* Intended for organizations or hosted deployments.

The architecture should support switching between these modes through configuration rather than requiring code changes.
