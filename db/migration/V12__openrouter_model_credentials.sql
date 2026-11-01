-- Preserve existing encrypted credentials while allowing the OpenRouter access channel.
ALTER TABLE backend_data.user_model_credentials
    DROP CONSTRAINT IF EXISTS user_model_credentials_provider_id_check;

ALTER TABLE backend_data.user_model_credentials
    ADD CONSTRAINT user_model_credentials_provider_id_check
    CHECK (provider_id IN ('openai', 'deepseek', 'openrouter'));
