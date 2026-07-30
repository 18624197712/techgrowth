# Split Chat and Embedding Provider Configuration

## Goal

Allow TechGrowth to use different OpenAI-compatible providers for chat and
embeddings. Each provider has its own base URL, model name, and API key. Both
base URLs include the provider's version path, such as `/v1`; TechGrowth
appends `/chat/completions` or `/embeddings` when making requests.

## Configuration Model

The setup API and web form expose two explicit provider groups:

- Chat: `base_url`, `model`, and `api_key`.
- Embedding: `base_url`, `model`, and `api_key`.

API keys remain write-only. Setup responses expose only
`api_key_configured` for each group. Saving an empty API key preserves the
existing encrypted key, allowing the user to edit a URL or model without
re-entering a secret.

The settings service stores six independently encrypted values under the
following keys:

- `provider.chat.base_url`
- `provider.chat.model`
- `provider.chat.api_key`
- `provider.embedding.base_url`
- `provider.embedding.model`
- `provider.embedding.api_key`

No schema migration is required because `app_settings` already uses arbitrary
string keys.

## Compatibility

The worker resolves configuration in this order:

1. New database values for the specific provider.
2. Legacy database values (`provider.base_url`, `provider.api_key`,
   `provider.chat_model`, and `provider.embedding_model`).
3. Provider-specific environment variables.
4. Legacy environment variables.

The new environment variables are:

- `TG_CHAT_BASE_URL`
- `TG_CHAT_API_KEY`
- `TG_CHAT_MODEL`
- `TG_EMBEDDING_BASE_URL`
- `TG_EMBEDDING_API_KEY`
- `TG_EMBEDDING_MODEL`

The existing `TG_OPENAI_BASE_URL` and `TG_OPENAI_API_KEY` remain supported as
fallbacks. Existing installations therefore keep working immediately after
the upgrade and can migrate through the settings page without downtime.

## Request Routing

`ModelClient.structured()` creates an HTTP client from the resolved chat
configuration and posts to `/chat/completions`.

`ModelClient.embedding()` creates an HTTP client from the resolved embedding
configuration and posts to `/embeddings`.

Each request sends only the API key belonging to that provider. Chat readiness
and embedding readiness are evaluated independently. Missing embedding
configuration must not prevent chat workflows from running, and missing chat
configuration must not cause an embedding request to use unrelated chat
credentials.

## Web Experience

The settings page shows two unambiguous sections: "聊天模型" and
"Embedding 模型". Each section contains a Base URL, model name, and password
field. A configured key is represented by a status indicator and a placeholder
explaining that an empty password field keeps the current key.

The workbench status distinguishes complete configuration from partial
configuration so the user can identify which provider still needs attention.

## Validation And Errors

Both Base URLs must be valid HTTP(S) URLs. Model names must be non-empty. A key
is required when that provider has no previously stored key, but an empty key
is accepted for updates that preserve an existing secret.

Provider failures remain isolated and identify the failing capability in the
error message. Existing token limits continue to apply across chat and
embedding calls made by one `ModelClient` instance.

## Testing

Backend tests must prove that:

- Chat and embedding requests use different URLs and Authorization headers.
- Each provider can be configured and reported independently.
- API responses never expose either key.
- Empty keys preserve existing encrypted secrets.
- Legacy database and environment configuration still resolves correctly.
- Missing provider-specific configuration produces a capability-specific
  error.

Frontend tests must prove that both configuration groups render, existing key
status is shown, and the submitted payload keeps the two providers separate.
The full API, web, lint, and production build suites must pass before release.

## Deployment

The change is backward compatible and requires no database migration. Build
and push new API and web images, update the ECS checkout, rebuild the two local
images using the server's working mirror configuration, restart the Compose
stack, and verify both provider requests against the configured services.
