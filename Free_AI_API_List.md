# Available Free AI APIs: Verified Notes


**How to read this file**
- Each provider section has the models, the limits, and a **Limit scope** line saying whether a limit is per model, per API key, per project/organization, or one shared pool.
- Each provider ends with a **Needs further verification** list. Anything listed there is not confirmed. Anything not listed anywhere is not included.
- Source tags: **[Official docs]** = read directly from the provider's own documentation. **[Dashboard]** = read from the account's own dashboard (Gemini numbers came from your AI Studio screenshots). **[Calculated]** = arithmetic from official numbers, with the assumption stated.

- When you see multiple API keys in .env you can be 100% sure that the API belong to different groq / gemini / openai accounts / cloudflare accounts (different organization). they are not API keys of same groq / gemini / openai / cloudflare account / organization. This is true for API keys of all AI API(Groq/google/openai etc.)


---

## Groq

**Source:** [Official docs] `console.groq.com/docs/rate-limits` and `console.groq.com/docs/models`.

**Limit scope**
- Limits are listed **per model**, and you hit whichever limit comes first.
- They are applied **per organization**, not per user, so extra API keys do not raise them.
- Cached tokens do not count toward limits.
- A rate-limited request returns HTTP 429 with a `retry-after` header.

**Column key:** RPM/RPD = requests per minute/day. TPM/TPD = tokens per minute/day. ASH/ASD = audio seconds per hour/day. K = thousand.

### Text generation

| Model ID | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 30 | 1K | 8K | 200K |
| `openai/gpt-oss-20b` | 30 | 1K | 8K | 200K |
| `qwen/qwen3.8-27b` | 30 | 1K | 8K | 200K |

### Safety / moderation models

| Model ID | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| `openai/gpt-oss-safeguard-20b` | 30 | 1K | 8K | 200K |
| `meta-llama/llama-prompt-guard-2-22m` | 30 | 14.4K | 15K | 500K |
| `meta-llama/llama-prompt-guard-2-86m` | 30 | 14.4K | 15K | 500K |

### Speech to text

| Model ID | RPM | RPD | ASH | ASD |
|---|---|---|---|---|
| `whisper-large-v3` | 20 | 2K | 7.2K | 28.8K |
| `whisper-large-v3-turbo` | 20 | 2K | 7.2K | 28.8K |

- 7.2K audio seconds per hour is 2 hours of audio per hour.
- 28.8K audio seconds per day is 8 hours of audio per day.

### Text to speech

| Model ID | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| `canopylabs/orpheus-v1-english` | 10 | 100 | 1.2K | 3.6K |
| `canopylabs/orpheus-arabic-saudi` | 10 | 100 | 1.2K | 3.6K |

### Not free

The docs list these as Enterprise / Contact Sales, so they are not in the free table:
- Llama 3.1 8B
- Llama 3.3 70B
- MiniMax M2.7

### Practical bottleneck
On the GPT-OSS and Qwen models, the 8K TPM cap is usually hit before the 30 RPM cap.

---

## Gemini (Google AI Studio)

**Sources**
- [Dashboard] verified-> Per-model numbers were read from `aistudio.google.com/rate-limit`, in the screenshots you shared.


**Limit scope**
- Limits are shown **per model** in AI Studio.
- Google's docs say they apply **per project, not per API key**, so extra keys in the same project don't help.
- RPD resets at **midnight Pacific time**.
- The limit types are RPM (requests/min), TPM (input tokens/min) and RPD (requests/day). Some models have extra limits.
- Preview and experimental models have tighter limits than stable ones.
- Google says listed limits are not guaranteed and actual capacity may vary.
- On the free tier, Google says your content is used to improve its products, so don't send private data.

Your numbers are for your own project. Other accounts may differ.

### Text and multimodal

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 3.5 Flash Lite | 15 | 250K | 500 |
| Gemini 3.1 Flash Lite | 15 | 250K | 500 |
| Gemini 2.5 Flash Lite | 10 | 250K | 20 |
| Gemini 3.8 Flash | 5 | 250K | 20 |
| Gemini 3.7 Flash | 5 | 250K | 20 |
| Gemini 3.6 Flash | 5 | 250K | 20 |
| Gemini 3.5 Flash | 5 | 250K | 20 |
| Gemini 3 Flash | 5 | 250K | 20 |
| Gemini 2.5 Flash | 5 | 250K | 20 |

### Gemma (open models)

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemma 4 31B | 30 | 16K | 14.4K |
| Gemma 4 26B | 30 | 16K | 14.4K |

### Live / real-time (voice)

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 3.8 Live | Unlimited | 65K | Unlimited |
| Gemini 3.8 Live Extended Thinking | Unlimited | 65K | Unlimited |
| Gemini 3 Flash Live | Unlimited | 65K | Unlimited |
| Gemini 2.5 Flash Native Audio Dialog | Unlimited | 1M | Unlimited |
| Gemini 3.5 Transcribe Live | Unlimited | 20K | Unlimited |
| Gemini 3.5 Live Translate | Unlimited | 20K | Unlimited |

### Speech to text and text to speech (non-live)

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 3.5 Transcribe | 3 | 10K | 25 |
| Gemini 3.8 Flash TTS | 3 | 10K | 10 |
| Gemini 3.8 Flash Lite TTS | 3 | 10K | 10 |
| Gemini 3.1 Flash TTS | 3 | 10K | 10 |
| Gemini 2.5 Flash TTS | 3 | 10K | 10 |

### Embeddings, robotics, agents

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini Embedding 2 | 100 | 30K | 1K |
| Gemini Embedding 1 | 100 | 30K | 1K |
| Gemini Robotics ER 2 Preview | 5 | 250K | 20 |
| Antigravity (agent) | 60 | 100K | 100 |

### Google Search grounding (Tools section of the dashboard)

| Models | RPD |
|---|---|
| Gemini 3.x | 0 |
| Gemini 2.5, Gemini 2, Default | 1.5K |

### Not usable on your account (all shown as 0)
- **Video, image and music:** Veo 3 (all three), Nano Banana (all four), Lyria 3 Pro and Clip, Gemini Omni Flash and 1.1 Flash.
- **Text and other:** Gemini 3.1 Pro, Gemini 2.5 Pro, Gemini 2.5 Pro TTS, Gemini 2 Flash and Flash Lite, Deep Research Pro Preview, Computer Use Preview.

### Other facts from Google's official pages
- **Paid tiers:** Tier 1 needs an active billing account. Tier 2 needs $100 paid plus 3 days. Tier 3 needs $1,000 paid plus 30 days.
- **Batch API:** the pricing page shows it free only for `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite`.
- **Search grounding on the pricing page:** not free for Gemini 3.x text models. Gemini 2.5 Flash gets up to 500 free grounded requests per day.

### Needs further verification
- **"Unlimited" on Live models** is what the dashboard shows. I have not seen it in Google's docs.
- **Search grounding vs model quota:** I assumed each grounded call also counts against the model's own daily limit (for example, 20/day on 2.5 Flash). This is an inference from the numbers, not documented.


---

## Cloudflare Workers AI

**Source:** [Official docs] the Pricing page and Limits page under `developers.cloudflare.com/workers-ai/platform/` (both last updated Sep 17, 2026).

**Limit scope**
- **One shared pool.** The free allocation is **10,000 Neurons per day in total**, shared across every model and task type. It is not per model.
- The pool resets daily at 00:00 UTC.
- On the free plan, exceeding a limit makes further operations fail with an error (per the docs). A third-party guide says it hard-stops instead of billing, which I did not see stated on the official page.
- Requests per minute are limited separately, **per task type** (and per model for a few models). See the table below.
- Overage is billed at $0.011 per 1,000 Neurons, on the Workers Paid plan only.
- Neuron cost varies a lot by model, so 10,000 Neurons is not a fixed number of requests.
- Local-mode inference through Wrangler also counts toward these limits. Beta models may have lower limits.

### Request-rate limits (Limits page)

| Task type | Limit |
|---|---|
| Text generation (models that don't require Workers Paid) | 300 requests/min |
| Text embeddings | 3,000 requests/min (`bge-large-en-v1.5`: 1,500) |
| Automatic speech recognition | 720 requests/min |
| Text-to-image | 720 requests/min |
| Image-to-text | 720 requests/min |
| Translation | 720 requests/min |
| Summarization | 1,500 requests/min |
| Text classification | 2,000 requests/min |
| Image classification | 3,000 requests/min |
| Object detection | 3,000 requests/min |

The limits page has no separate category for text-to-speech, so I don't have a request limit for those models.

### Models that need a paid plan (not usable for free)
The docs say these need either Workers Paid or prepaid AI Gateway credits:
- `@cf/moonshotai/kimi-k2.6`
- `@cf/moonshotai/kimi-k2.7-code`
- `@cf/zai-org/glm-5.2`
- `@cf/zai-org/glm-5.3`
- `@cf/zai-org/glm-5.3-flash`
- `@cf/deepseek-ai/deepseek-v4-flash-0731`
- `@cf/deepseek-ai/deepseek-v4-pro-0813`

Their rate limit is 20 requests/min on standard billing and 50 requests/min with prepaid AI Gateway credits. The docs do not label any other model as "free". I treat the rest of the pricing page as free-eligible because only these seven carry the paid-plan note.

### Text generation (LLM) models

- **Neuron cost** is from the pricing page [Official docs].
- **Requests/day** is [Calculated]: 10,000 divided by the Neurons for one request of 500 input and 500 output tokens. It assumes the whole pool goes to that one model. Real prompts will differ.

| Model | Neurons per M input tokens | Neurons per M output tokens | ≈ Requests/day |
|---|---|---|---|
| `@cf/ibm-granite/granite-4.0-h-micro` | 1,542 | 10,158 | ~1,700 |
| `@cf/meta/llama-3.2-1b-instruct` | 2,457 | 18,252 | ~970 |
| `@cf/mistral/mistral-7b-instruct-v0.1` | 10,000 | 17,300 | ~730 |
| `@cf/qwen/qwen3-30b-a3b-fp8` | 4,625 | 30,475 | ~570 |
| `@cf/meta/llama-3.2-3b-instruct` | 4,625 | 30,475 | ~570 |
| `@cf/meta/llama-3.1-8b-instruct-awq` | 11,161 | 24,215 | ~565 |
| `@cf/meta/llama-3-8b-instruct-awq` | 11,161 | 24,215 | ~565 |
| `@cf/google/gemma-4-26b-a4b-it` | 9,091 | 27,273 | ~550 |
| `@cf/meta/llama-3.1-8b-instruct-fp8-fast` | 4,119 | 34,868 | ~510 |
| `@cf/meta/llama-3.1-8b-instruct-fp8` | 13,778 | 26,128 | ~500 |
| `@cf/zai-org/glm-4.7-flash` | 5,500 | 36,400 | ~480 |
| `@cf/openai/gpt-oss-20b` | 18,182 | 27,273 | ~440 |
| `@cf/meta/llama-guard-3-8b` | 44,003 | 2,730 | ~430 |
| `@cf/meta/llama-3.2-11b-vision-instruct` | 4,410 | 61,493 | ~300 |
| `@cf/mistralai/mistral-small-3.1-24b-instruct` | 31,876 | 50,488 | ~240 |
| `@cf/aisingapore/gemma-sea-lion-v4-27b-it` | 31,876 | 50,488 | ~240 |
| `@cf/google/gemma-3-12b-it` | 31,371 | 50,560 | ~240 |
| `@cf/openai/gpt-oss-120b` | 31,818 | 68,182 | ~200 |
| `@cf/meta/llama-3.1-8b-instruct` | 25,608 | 75,147 | ~200 |
| `@cf/meta/llama-3-8b-instruct` | 25,608 | 75,147 | ~200 |
| `@cf/meta/llama-4-scout-17b-16e-instruct` | 24,545 | 77,273 | ~200 |
| `@cf/qwen/qwq-32b` | 60,000 | 90,909 | ~130 |
| `@cf/qwen/qwen2.5-coder-32b-instruct` | 60,000 | 90,909 | ~130 |
| `@cf/nvidia/nemotron-3-120b-a12b` | 45,455 | 136,364 | ~110 |
| `@cf/meta/llama-3.1-70b-instruct-fp8-fast` | 26,668 | 204,805 | ~85 |
| `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | 26,668 | 204,805 | ~85 |
| `@cf/qwen/qwen3.8-27b` | 40,909 | 290,909 | ~60 |
| `@cf/moonshotai/kimi-k2.5` | 54,545 | 272,727 | ~60 |
| `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` | 45,170 | 443,756 | ~40 |
| `@cf/meta/llama-2-7b-chat-fp16` | 50,505 | 606,061 | ~30 |

### Embeddings

Tokens per day is [Calculated] as 10,000 divided by the Neuron cost per million tokens. Limit: 3,000 requests/min (`bge-large-en-v1.5`: 1,500).

| Model | Neurons per M input tokens | ≈ Tokens/day |
|---|---|---|
| `@cf/baai/bge-m3` | 1,075 | ~9.3M |
| `@cf/qwen/qwen3-embedding-0.6b` | 1,075 | ~9.3M |
| `@cf/pfnet/plamo-embedding-1b` | 1,689 | ~5.9M |
| `@cf/baai/bge-small-en-v1.5` | 1,841 | ~5.4M |
| `@cf/baai/bge-base-en-v1.5` | 6,058 | ~1.65M |
| `@cf/baai/bge-large-en-v1.5` | 18,582 | ~540K |

### Speech to text

Limit: 720 requests/min for automatic speech recognition. Minutes per day is [Calculated].

| Model | Neurons per audio minute | ≈ Minutes/day |
|---|---|---|
| `@cf/openai/whisper` | 41.14 | ~243 |
| `@cf/openai/whisper-large-v3-turbo` | 46.63 | ~214 |
| `@cf/deepgram/nova-3` | 472.73 | ~21 |
| `@cf/deepgram/nova-3` (WebSocket) | 836.36 | ~12 |
| `@cf/deepgram/flux` (WebSocket) | 700.00 | ~14 |
| `@cf/pipecat-ai/smart-turn-v2` | 0.51 | pricing lists it, use not verified |

### Text to speech

There is no request-rate limit on the Limits page for this category. Amounts per day are [Calculated].

| Model | Neuron cost | ≈ Amount/day |
|---|---|---|
| `@cf/myshell-ai/melotts` | 18.63 per audio minute | ~536 min |
| `@cf/deepgram/aura-1` | 1,363.64 per 1K characters | ~7,300 characters |
| `@cf/deepgram/aura-2-en` | 2,727.27 per 1K characters | ~3,700 characters |
| `@cf/deepgram/aura-2-es` | 2,727.27 per 1K characters | ~3,700 characters |

### Image generation

Limit: 720 requests/min for text-to-image (`stable-diffusion-v1-5-img2img` is 1,500).

| Model | Neuron cost |
|---|---|
| `@cf/black-forest-labs/flux-1-schnell` | 4.80 per 512×512 tile, 9.60 per step |
| `@cf/black-forest-labs/flux-2-klein-4b` | 5.37 per input 512×512 tile, 26.05 per output 512×512 tile |
| `@cf/black-forest-labs/flux-2-dev` | 18.75 per input tile per step, 37.50 per output tile per step |
| `@cf/leonardo/phoenix-1.0` | 530 per 512×512 tile, 10 per step |
| `@cf/leonardo/lucid-origin` | 636 per 512×512 tile, 12 per step |
| `@cf/black-forest-labs/flux-2-klein-9b` | 1,363.64 per first MP (1024×1024), 181.82 per extra MP, 181.82 per input-image MP |

### Vision, translation, classification, other

| Model | Neuron cost |
|---|---|
| `@cf/moondream/moondream3.1-9B-A2B` | 27,273 per M input tokens, 90,909 per M output tokens |
| `@cf/meta/m2m100-1.2b` (translation) | 31,050 per M tokens in and out |
| `@cf/ai4bharat/indictrans2-en-indic-1B` (translation) | 31,050 per M tokens in and out |
| `@cf/huggingface/distilbert-sst-2-int8` | 2,394 per M input tokens |
| `@cf/baai/bge-reranker-base` | 283 per M input tokens |
| `@cf/microsoft/resnet-50` | 228,055 per M images |

### Needs further verification
- **"Free-eligible" is inferred.** The docs never label models "free". I inferred it from the seven-model paid list. Test each model with one call before depending on it.
- **Context window and max output tokens** per model are not on the Pricing or Limits pages. They are on each model's catalog page, which I did not check.
- **Coverage:** the pricing page may not list every model in the catalog. Third-party sources mention around 80 models. I only include what the pricing page lists.
- **Image billing:** it is unclear whether the per-tile and per-step charges add up for `flux-1-schnell`, so I gave no images-per-day figure. Test one generation and read the Neurons used in the Workers AI dashboard (`dash.cloudflare.com`).
- **Task-type mapping:** I did not check which task type each model belongs to. I assumed the obvious ones (LLMs as text generation, embeddings as text embeddings). Deepgram and other audio models may map to different limits.
- **Signup:** credit-card requirement and availability from Bangladesh were not verified. One third-party guide says no card is needed.
- **Calculated columns** use one assumed usage pattern (500 input + 500 output tokens). Your real prompts will change the numbers.

---

## Quick comparison: how each provider's limit works

| Provider | Limit is per… | Resets | Main constraint |
|---|---|---|---|
| Groq | Model, applied per organization | Per minute and per day (reset time not checked) | TPM (8K on the main text models) |
| Gemini | Model, applied per project | RPD at midnight Pacific | RPD (20 on the full Flash models) |
| Cloudflare | One shared 10,000-Neuron pool per account, plus a per-task-type RPM | Daily at 00:00 UTC | Neurons per day |