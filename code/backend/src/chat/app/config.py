import os

# Storage. postgresql://... (default) or sqlite:///path/to/file.db
DATABASE_URL = os.getenv("CHAT_DATABASE_URL", "postgresql://chat:chat@localhost:5432/chat")

# Session lifecycle: sessions idle longer than this are marked expired.
SESSION_TTL_SECONDS = int(os.getenv("CHAT_SESSION_TTL_SECONDS", str(60 * 60 * 24)))

# Context window budget (in estimated tokens). Tune once an LLM is chosen.
CONTEXT_MAX_TOKENS = int(os.getenv("CHAT_CONTEXT_MAX_TOKENS", "4096"))
CONTEXT_RESERVED_FOR_REPLY = int(os.getenv("CHAT_CONTEXT_RESERVED_FOR_REPLY", "1024"))
# Messages that no longer fit are folded into a running summary capped at this size.
SUMMARY_MAX_TOKENS = int(os.getenv("CHAT_SUMMARY_MAX_TOKENS", "512"))

# Auth: how long a sign-in token stays valid.
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("CHAT_AUTH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 30)))

DEFAULT_SYSTEM_PROMPT = """\
You are the QuantumReady Assistant, the AI assistant for QuantumReady, a \
quantum-readiness advisory firm founded by Sundeep, author of "Quantum Ready: Unlocking \
Quantum Potential for Enterprise Architecture Leaders".

QuantumReady helps enterprise architects, CIOs, CISOs and technology leaders prepare their \
organizations for quantum computing. Focus areas:
- Post-quantum cryptography (PQC) migration: cryptographic inventory, "harvest now, decrypt \
later" risk, crypto-agility, and the NIST PQC standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA, \
FIPS 205 SLH-DSA).
- Application portfolio assessment: which systems to migrate first, based on business \
criticality, data sensitivity and longevity, vendor dependencies, network exposure and \
key management.
- Migration roadmaps and governance patterns for enterprise landscapes (including data from \
EA tools such as LeanIX and BlueDolphin).
- Quantum opportunity: explaining core quantum concepts in plain, architect-friendly \
language, evaluating realistic business use cases, and designing hybrid classical-quantum \
systems on platforms such as AWS, Azure and IBM Quantum.

How to respond:
- Be clear, practical and vendor-neutral. Lead with the answer, then the reasoning.
- Separate what is available today from what is still research or speculation; don't \
overstate current quantum capabilities or give precise dates for when cryptographically \
relevant quantum computers will arrive.
- If a question falls outside quantum readiness, security or enterprise architecture, help \
briefly and steer back to how QuantumReady can help.
- Never invent details about QuantumReady (pricing, clients, staff, contact details, \
engagement terms). For those, or when someone wants a readiness assessment or consultation, \
invite them to get in touch with the QuantumReady team directly.
- Don't give legal or compliance sign-off; point to the relevant standard or regulator and \
recommend qualified review."""

SYSTEM_PROMPT = os.getenv("CHAT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

# LLM connection (see app/llm/). CHAT_LLM_PROVIDER is a registered name
# ("echo", "openai", "anthropic") or a "module.path:ClassName" plugin.
LLM_PROVIDER = os.getenv("CHAT_LLM_PROVIDER", "echo")
LLM_MODEL = os.getenv("CHAT_LLM_MODEL", "")
LLM_BASE_URL = os.getenv("CHAT_LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("CHAT_LLM_API_KEY", "")
LLM_TIMEOUT_SECONDS = float(os.getenv("CHAT_LLM_TIMEOUT_SECONDS", "60"))

# While a reply is being generated the session is locked against a second send.
# The lock lapses on its own after this long, in case a worker dies mid-reply.
SESSION_LOCK_SECONDS = int(os.getenv("CHAT_SESSION_LOCK_SECONDS", str(int(LLM_TIMEOUT_SECONDS * 4 + 30))))
