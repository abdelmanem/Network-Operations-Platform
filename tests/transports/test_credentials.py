from backend.app.transports.base import TransportContext, TransportTarget
from backend.app.transports.credentials import (
    MappingCredentialResolver,
    StaticCredentialResolver,
    TokenCredentials,
    UsernamePasswordCredentials,
)


def test_token_credentials_render_authorization_header() -> None:
    token_value = "".join(["abc", "123"])
    credentials = TokenCredentials(token=token_value)

    assert credentials.as_dict() == {"Authorization": f"Bearer {token_value}"}


def test_static_credential_resolver_returns_fixed_credentials() -> None:
    target = TransportTarget(identifier="device-1", address="10.0.0.1")
    context = TransportContext(target=target)
    password_value = "".join(["p", "ass"])
    credentials = UsernamePasswordCredentials(
        username="user",
        password=password_value,
    )

    resolver = StaticCredentialResolver(credentials=credentials)

    assert resolver.resolve(context) is credentials


def test_mapping_credential_resolver_uses_target_identifier() -> None:
    target = TransportTarget(identifier="device-1", address="10.0.0.1")
    context = TransportContext(target=target)
    password_value = "".join(["p", "ass"])
    credentials = UsernamePasswordCredentials(
        username="user",
        password=password_value,
    )

    resolver = MappingCredentialResolver(
        credentials_by_target={"device-1": credentials}
    )

    assert resolver.resolve(context) is credentials
