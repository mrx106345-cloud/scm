# Model Selection — SCM Agent

This document records the chosen local language model and licensing terms for the SCM Agent system.

## Chosen Model

| Property | Value |
|---|---|
| **Model** | Qwen2.5-3B-Instruct (GGUF, 4-bit quantized) |
| **File size** | ~2 GB |
| **Peak RAM** | ~4 GB (within the 4 GB limit per tech-stack §81) |
| **Context length** | 4096 tokens |
| **Temperature** | 0.2 (0 on retry) |
| **Output format** | JSON with schema; never raw numbers or decisions |

## License

The model file (Qwen2.5-3B-Instruct-Q4_K_M.gguf) must have a license that permits:
- Commercial redistribution inside a paid product
- Modification and derivative works
- Use as a local, offline inference engine only

The owner must approve the model choice and record the specific license terms in this file before any production deployment.

*Until a model is selected and licensed, the system operates with `MockBackend` only, which is deterministic, testable, and produces no runtime dependency on a model file (per tech-stack §87).*

## Model Policy (tech-stack.md compliance)

- ✅ Size about 2 GB, 4-bit quantized GGUF
- ✅ Peak RAM at most 4 GB
- ✅ CPU-only; AVX2 detection in pre-check (warn if unsupported)
- ✅ No GPU-only libraries (CUDA-required builds forbidden per tech-stack §97)
- ✅ Interface: `LLMBackend` protocol so models and runtimes can be swapped (§86)
- ✅ Tests use `MockBackend` in unit tests; real model only in `llm_bench` and a few integration tests (§87)

*Owner approval required before bundling any model file. The agent must not download or bundle a model without explicit owner approval (tech-stack §82).*

---
*Generated: 2026-10-23. Update when model is finalized and licensed.*