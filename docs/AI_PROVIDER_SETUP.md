# AI provider setup

The optional provider accepts an OpenAI-compatible Base URL, API key and a
manual or refreshed model name. Auto mode may try Responses then Chat
Completions only for unsupported endpoint responses; it does not retry 401 or
403 with another endpoint. API keys are redacted from UI errors and logs.

Use connection/model refresh actions deliberately. Automated tests use mock
transports and do not call paid providers.
