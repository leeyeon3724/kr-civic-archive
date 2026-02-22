from __future__ import annotations

from types import SimpleNamespace

from app.security_access import build_metrics_access_dependencies, build_protected_dependencies


def test_build_protected_dependencies_preserves_dependency_order():
    config = SimpleNamespace(REQUIRE_API_KEY=False, REQUIRE_JWT=False)

    def api_builder(_config):
        async def api_dependency():
            return None

        return api_dependency

    def jwt_builder(_config):
        async def jwt_dependency():
            return None

        return jwt_dependency

    def rate_limit_builder(_config):
        async def rate_limit_dependency():
            return None

        return rate_limit_dependency

    dependencies = build_protected_dependencies(
        config,
        build_api_key_dependency=api_builder,
        build_jwt_dependency=jwt_builder,
        build_rate_limit_dependency=rate_limit_builder,
    )

    assert len(dependencies) == 3
    assert dependencies[0].dependency.__name__ == "api_dependency"
    assert dependencies[1].dependency.__name__ == "jwt_dependency"
    assert dependencies[2].dependency.__name__ == "rate_limit_dependency"


def test_build_metrics_access_dependencies_respects_auth_flags():
    config = SimpleNamespace(REQUIRE_API_KEY=True, REQUIRE_JWT=False)

    def api_builder(_config):
        async def api_dependency():
            return None

        return api_dependency

    def jwt_builder(_config):
        async def jwt_dependency():
            return None

        return jwt_dependency

    dependencies = build_metrics_access_dependencies(
        config,
        build_api_key_dependency=api_builder,
        build_jwt_dependency=jwt_builder,
    )

    assert len(dependencies) == 1
    assert dependencies[0].dependency.__name__ == "api_dependency"
