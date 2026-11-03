"""Probe a provider with one bounded model call without storing a candidate Key."""

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.schemas.model_credential import ModelCredentialTestResult
from app.services import model_catalog, model_credential_service, model_service


async def test_credential(user_id: int, provider_id: str,
                          candidate_key: str | None) -> ModelCredentialTestResult:
    if provider_id not in model_credential_service.PROVIDER_IDS:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "不支持的模型提供商")
    model = next((item for item in model_catalog.load_catalog().models
                  if item.enabled and item.providerId == provider_id and item.askSupported), None)
    if model is None:
        raise BusinessError(400, ErrorCode.PARAMS_ERROR, "该提供商当前没有可测试的模型")
    if candidate_key is None:
        key = model_credential_service.resolve_api_key(user_id, provider_id)
        if key is None:
            raise BusinessError(400, ErrorCode.PARAMS_ERROR, "请先输入或保存 API Key")
    else:
        key = model_credential_service.normalize_api_key(candidate_key)

    try:
        probe = model_service.build_chat_model(model, key, timeout=20, max_tokens=32, max_retries=0)
        await probe.ainvoke("请只回复 OK。")
    except Exception as error:
        status_code = getattr(error, "status_code", None)
        if status_code in (401, 403):
            status, message = "invalid", "API Key 无效、已过期或无权访问该模型"
        elif status_code == 402:
            status, message = "unavailable", "提供商账户额度不足，暂时无法确认模型调用"
        elif status_code == 429:
            status, message = "unavailable", "提供商正在限流，请稍后重试"
        else:
            status, message = "unavailable", "暂时无法连接模型服务，请稍后重试"
        return ModelCredentialTestResult(providerId=provider_id, modelId=model.id,
                                         status=status, message=message)
    return ModelCredentialTestResult(providerId=provider_id, modelId=model.id,
                                     status="valid", message="连接成功，模型可以使用此 Key")
