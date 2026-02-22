import app.security as security


def test_redis_rate_limiter_fail_open_enters_cooldown(monkeypatch):
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        @staticmethod
        def script_load(_script):
            return "sha"

        def evalsha(self, _sha, _num_keys, _redis_key, _ttl):
            self.calls += 1
            raise security.RedisError("redis down")

    fake_client = FakeClient()

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(_redis_url, **_kwargs):
                return fake_client

    monkeypatch.setattr(security, "redis", FakeRedisModule)

    limiter = security.RedisRateLimiter(
        requests_per_minute=1,
        redis_url="redis://localhost:6379/0",
        key_prefix="test",
        window_seconds=60,
        failure_cooldown_seconds=30,
        fail_open=True,
    )

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert fake_client.calls == 1


def test_redis_rate_limiter_fail_closed_enters_cooldown(monkeypatch):
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        @staticmethod
        def script_load(_script):
            return "sha"

        def evalsha(self, _sha, _num_keys, _redis_key, _ttl):
            self.calls += 1
            raise security.RedisError("redis down")

    fake_client = FakeClient()

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(_redis_url, **_kwargs):
                return fake_client

    monkeypatch.setattr(security, "redis", FakeRedisModule)

    limiter = security.RedisRateLimiter(
        requests_per_minute=1,
        redis_url="redis://localhost:6379/0",
        key_prefix="test",
        window_seconds=60,
        failure_cooldown_seconds=30,
        fail_open=False,
    )

    assert limiter.allow("client-a") is False
    assert limiter.allow("client-a") is False
    assert fake_client.calls == 1
