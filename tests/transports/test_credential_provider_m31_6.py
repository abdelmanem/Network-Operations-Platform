from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

import pytest
from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
    TransportTarget,
)
from backend.app.transports.credentials import (
    CredentialReference,
    CredentialResolutionError,
    ProfileSecretCredentialProvider,
    SNMPv2cCredentials,
    UsernamePasswordCredentials,
)
from backend.app.transports.manager import TransportManager
from backend.app.transports.secret_errors import SecretNotFoundError
from backend.app.transports.session import TransportSession


@dataclass(slots=True)
class Profile:
    id: UUID
    tenant_id: str
    provider_reference: str
    transport_types: list[str]
    credential_type: str | None
    username: str | None
    enabled: bool = True


@dataclass(slots=True)
class StubSecretProvider:
    secret: str = "runtime-secret"
    calls: list[str] | None = None

    def resolve_secret(self, reference: str) -> str:
        if self.calls is not None:
            self.calls.append(reference)
        return self.secret


def _reference(profile: Profile, transport: str = "ssh") -> CredentialReference:
    return CredentialReference(profile.id, transport, profile.tenant_id)


def test_profile_provider_resolves_profile_reference_to_ssh_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    profile = Profile(
        uuid4(), "tenant-a", "vault/cisco-prod", ["ssh"], "ssh_password", "netops"
    )
    calls: list[str] = []
    provider = ProfileSecretCredentialProvider(
        StubSecretProvider(calls=calls),
        lambda tenant_id, profile_id: (
            profile
            if (tenant_id, profile_id) == (profile.tenant_id, profile.id)
            else None
        ),
    )

    credentials = provider.resolve_reference(_reference(profile))

    assert credentials == UsernamePasswordCredentials("netops", "runtime-secret")
    assert calls == ["vault/cisco-prod"]
    assert "runtime-secret" not in _reference(profile).as_dict().values()
    assert "runtime-secret" not in asdict(profile).values()
    assert "runtime-secret" not in caplog.text


def test_profile_provider_constructs_snmpv2c_credentials() -> None:
    profile = Profile(uuid4(), "tenant-a", "vault/snmp", ["snmp"], "snmp_v2c", None)
    provider = ProfileSecretCredentialProvider(
        StubSecretProvider(), lambda _tenant_id, _profile_id: profile
    )

    assert provider.resolve_reference(
        _reference(profile, "pysnmp")
    ) == SNMPv2cCredentials("runtime-secret")


def test_profile_provider_rejects_missing_profile_with_tenant_scoped_loader() -> None:
    profile = Profile(
        uuid4(), "tenant-a", "vault/unused", ["ssh"], "ssh_password", "netops"
    )
    calls: list[tuple[str, UUID]] = []
    provider = ProfileSecretCredentialProvider(
        StubSecretProvider(),
        lambda tenant_id, profile_id: calls.append((tenant_id, profile_id)) or None,
    )

    with pytest.raises(CredentialResolutionError, match="not found"):
        provider.resolve_reference(_reference(profile))

    assert calls == [("tenant-a", profile.id)]


def test_profile_provider_enforces_tenant_isolation() -> None:
    profile = Profile(uuid4(), "tenant-a", "vault/a", ["ssh"], "ssh_password", "netops")
    provider = ProfileSecretCredentialProvider(
        StubSecretProvider(),
        lambda tenant_id, profile_id: (
            profile if (tenant_id, profile_id) == ("tenant-a", profile.id) else None
        ),
    )

    with pytest.raises(CredentialResolutionError, match="not found"):
        provider.resolve_reference(
            CredentialReference(profile.id, "ssh", tenant_id="tenant-b")
        )


def test_profile_provider_propagates_missing_secret_without_credentials() -> None:
    profile = Profile(
        uuid4(), "tenant-a", "vault/missing", ["ssh"], "ssh_password", "netops"
    )

    class MissingSecretProvider:
        def resolve_secret(self, _reference: str) -> str:
            raise SecretNotFoundError("Requested secret was not found.")

    provider = ProfileSecretCredentialProvider(
        MissingSecretProvider(), lambda _tenant_id, _profile_id: profile
    )

    with pytest.raises(SecretNotFoundError):
        provider.resolve_reference(_reference(profile))


def test_profile_provider_rejects_unsupported_transport_before_secret_lookup() -> None:
    profile = Profile(
        uuid4(), "tenant-a", "vault/unused", ["ssh"], "ssh_password", "netops"
    )
    calls: list[str] = []
    provider = ProfileSecretCredentialProvider(
        StubSecretProvider(calls=calls), lambda _tenant_id, _profile_id: profile
    )

    with pytest.raises(CredentialResolutionError, match="support"):
        provider.resolve_reference(_reference(profile, "telnet"))

    assert calls == []


class CountingTransport(BaseTransport):
    name = "ssh"
    capabilities = frozenset({TransportCapability.SSH})

    def __init__(self) -> None:
        self.created = 0

    def health_check(self, context: TransportContext) -> None:
        return None

    def create_session(self, context: TransportContext) -> TransportSession:
        self.created += 1
        raise AssertionError("session creation must not be reached")

    def close(self) -> None:
        return None


@pytest.mark.anyio
async def test_missing_secret_stops_before_transport_session_creation() -> None:
    profile = Profile(
        uuid4(), "tenant-a", "vault/missing", ["ssh"], "ssh_password", "netops"
    )

    class MissingSecretProvider:
        def resolve_secret(self, _reference: str) -> str:
            raise SecretNotFoundError("Requested secret was not found.")

    transport = CountingTransport()
    manager = TransportManager(
        credential_provider=ProfileSecretCredentialProvider(
            MissingSecretProvider(), lambda _tenant_id, _profile_id: profile
        )
    )
    manager.register(transport)

    with pytest.raises(SecretNotFoundError):
        await manager.open_session(
            "ssh",
            TransportTarget(
                "switch-01", "10.0.0.1", credential_reference=_reference(profile)
            ),
        )

    assert transport.created == 0
