"""One atomic fixed-window decision per authenticated cloud command."""
from dataclasses import dataclass
from typing import Literal

from django.conf import settings
from django.core.cache import cache
from django.core.cache.backends.redis import RedisCache
from redis import Redis

from . import services
from .services import BudgetOutcome

BudgetKind = Literal["admission", "renewal", "quota"]
WINDOW = 3600
_LIMITS = {"admission": (30, 10), "renewal": (30, 15), "quota": (120,)}

_SCRIPT = """
local ttl, counts, retry = {}, {}, 0
for i, key in ipairs(KEYS) do
    ttl[i] = redis.call('PTTL', key)
    local raw = redis.call('GET', key)
    if raw then
        if #raw > 10 or not string.match(raw, '^[1-9][0-9]*$') or tonumber(raw) > 2147483647 then
            return redis.error_reply('ERR invalid cloud counter')
        end
        counts[i] = tonumber(raw)
    else
        counts[i] = 0
    end
    if counts[i] >= tonumber(ARGV[i+1]) then
        local hint = ttl[i] < 0 and 3600 or math.max(1, math.min(3600, math.ceil(ttl[i] / 1000)))
        retry = math.max(retry, hint)
    end
end
for i, key in ipairs(KEYS) do
    if ttl[i] == -1 then
        redis.call('EXPIRE', key, ARGV[1])
    end
    if retry == 0 then
        if counts[i] == 0 then
            redis.call('SET', key, 1, 'EX', ARGV[1])
        else
            redis.call('INCR', key)
        end
    end
end
return retry
"""


@dataclass(frozen=True, slots=True)
class CloudBudgetDecision:
    outcome: BudgetOutcome
    retry_after_seconds: int | None


def _raw_keys(org_id: int, device_id: int, kind: BudgetKind) -> tuple[str, ...]:
    if any(type(pk) is not int or pk <= 0 for pk in (org_id, device_id)):
        raise ValueError("Invalid cloud budget identity")
    prefix = f"cloud:v1:{{org:{org_id}}}:{kind}"
    device = f"{prefix}:device:{device_id}"
    return (device,) if kind == "quota" else (f"{prefix}:org", device)


def _eval_budget(org_id: int, device_id: int, kind: BudgetKind) -> int:
    backend = services.CacheStore(cache)._cache
    location = settings.CACHES.get("default", {}).get("LOCATION")
    if type(backend) is not RedisCache or not isinstance(location, str) or not location.startswith(
        ("redis://", "rediss://", "unix://")
    ):
        raise ValueError("Unsupported cloud budget backend")
    raw = _raw_keys(org_id, device_id, kind)
    keys = tuple(backend.make_and_validate_key(key) for key in raw)
    tag = f"{{org:{org_id}}}"
    if any(key.find("{") != key.find(tag) or not key.endswith(original) for key, original in zip(keys, raw)):
        raise ValueError("Invalid cloud budget key prefix")
    client = backend._cache.get_client(keys[0], write=True)
    if type(client) is not Redis:
        raise ValueError("Unsupported cloud budget client")
    # redis-py's normal execute_command may retry after a lost reply. A budget
    # command cannot be replayed safely, even on a single primary.
    pool = client.connection_pool
    connection = pool.get_connection()
    try:
        connection.send_command("EVAL", _SCRIPT, len(keys), *keys, WINDOW, *_LIMITS[kind])
        result = connection.read_response()
    except BaseException:
        connection.disconnect()
        raise
    finally:
        pool.release(connection)
    if type(result) is not int or not 0 <= result <= WINDOW:
        raise ValueError("Invalid cloud budget response")
    return result


def evaluate_cloud_budget(*, org_id: int, device_id: int, kind: BudgetKind) -> CloudBudgetDecision:
    circuit = services.CACHE_CIRCUIT
    token = circuit.admit()
    if token is None:
        services._report_store_unavailable("CircuitOpen")
        return CloudBudgetDecision(BudgetOutcome.STORE_UNAVAILABLE, WINDOW)
    success = False
    try:
        hint = _eval_budget(org_id, device_id, kind)
        success = True
    except Exception as error:
        services._report_store_unavailable(type(error).__name__)
        return CloudBudgetDecision(BudgetOutcome.STORE_UNAVAILABLE, WINDOW)
    finally:
        circuit.finish(
            token, success=success, threshold=settings.CACHE_CIRCUIT_FAILURE_THRESHOLD,
            cooldown=settings.CACHE_CIRCUIT_COOLDOWN,
        )
    return CloudBudgetDecision(BudgetOutcome.DENIED, hint) if hint else CloudBudgetDecision(
        BudgetOutcome.ALLOWED, None,
    )
