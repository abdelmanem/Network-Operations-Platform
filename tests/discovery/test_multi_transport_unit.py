import asyncio
from uuid import uuid4

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.contracts import DiscoveryFailureCode, DiscoveryJobStatus
from backend.app.discovery.execution import (
    DiscoveryExecutionService,
    DiscoveryTargetRecordView,
)
from backend.app.discovery.result_states import DiscoveryResultState
from backend.app.models.base import BaseModel
from backend.app.persistence.discovery_repositories import DiscoveryJobRepository
from backend.app.persistence.models import (
    CredentialProfileRecord,
    DiscoveryDeviceResultRecord,
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


class SshSuccessCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        await asyncio.sleep(0.01)
        return {
            "hostname": context.target.identifier,
            "transport": "ssh",
            "platform_family": "cisco-iosxe",
            "facts": {"serial": "SSH-SERIAL-1"},
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class CiscoRawPayloadCollector(BaseCollector):
    parser = CiscoInventoryParser()

    def __init__(
        self,
        *,
        payload: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(
            name="cisco-raw",
            capabilities=frozenset({CollectorCapability.SSH}),
        )
        self.payload = payload
        self.error = error

    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        if self.error is not None:
            raise self.error
        return self.payload or {
            "target": {
                "identifier": context.target.identifier,
                "address": context.target.address,
                "metadata": {},
            },
            "platform_family": "catalyst-2960",
            "parser_family": "ios",
            "transport": "ssh",
            "commands": {
                "show version": (
                    "Cisco IOS Software, C2960 Software, Version 15.2(7)E7\n"
                    "New-Ground-SW1 uptime is 1 day\n"
                    "Model number                    : WS-C2960-48TT-L\n"
                    "System serial number            : FOC1234X1AB\n"
                ),
                "show inventory": (
                    'NAME: "1", DESCR: "Switch"\n'
                    "PID: WS-C2960-48TT-L , VID: V05 , SN: FOC1234X1AB"
                ),
            },
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        from backend.app.parsers.context import ParserContext, ParserInputFormat

        result = self.parser.parse(
            ParserContext(
                source=context.target.identifier,
                input_format=ParserInputFormat.JSON,
                parser_name=self.parser.name,
            ),
            raw_payload,
        )
        from backend.app.normalization.engine import NormalizationEngine

        return NormalizationEngine().normalize(result).snapshot

    async def close(self) -> None:
        return None


class SshAuthFailCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise RuntimeError("Authentication failed: invalid credentials for SSH")

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class SshTimeoutCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise TimeoutError("Connection timed out - host unreachable")

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class GenericDiscoveryFailCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise RuntimeError("Collector failed during discovery processing")

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class SshFailReachableCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise ConnectionRefusedError("Connection refused - SSH service not available")

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class TelnetSuccessCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        await asyncio.sleep(0.01)
        return {
            "hostname": context.target.identifier,
            "transport": "telnet",
            "platform_family": "cisco-iosxe",
            "facts": {"serial": "TELNET-SERIAL-1"},
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class TelnetFailCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise ConnectionRefusedError(
            "Connection refused - Telnet service not available"
        )

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class HttpsSuccessCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        await asyncio.sleep(0.01)
        return {
            "hostname": context.target.identifier,
            "transport": "https",
            "platform_family": "cisco-iosxe",
            "facts": {"serial": "HTTPS-SERIAL-1"},
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class HttpsFailCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise ConnectionRefusedError("Connection refused - HTTPS service not available")

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class HttpSuccessCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        return {
            "hostname": context.target.identifier,
            "transport": "http",
            "platform_family": "cisco-iosxe",
            "facts": {"serial": "HTTP-SERIAL-1"},
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


class SnmpCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise AssertionError(
            "SNMP should not be called in unsupported-credential scenario"
        )

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Must not normalize in unit tests")

    async def close(self) -> None:
        return None


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


def _credential_profile(
    session: Session,
    *,
    transport_types: list[str] | None = None,
    credential_type: str | None = None,
) -> CredentialProfileRecord:
    if transport_types is None:
        transport_types = ["ssh", "telnet", "https"]
    profile = CredentialProfileRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        name="test-profile",
        credential_type=credential_type or "ssh_password",
        transport_types=transport_types,
        provider_reference="vault:secret/test",
    )
    session.add(profile)
    session.flush()
    return profile


def _job_with_profile(
    session: Session,
    *,
    profile: CredentialProfileRecord | None = None,
    address: str = "10.0.0.1",
    identifier: str = "core-01",
    allow_insecure_telnet: bool = True,
    fallback_transports: list[str] | None = None,
    collector_name: str = "",
) -> DiscoveryJobRecord:
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier=identifier,
        address=address,
        enabled=True,
        credential_reference="credential:fake",
        credential_profile_id=str(profile.id) if profile else None,
        allow_insecure_telnet=allow_insecure_telnet,
        allowed_fallback_transports=fallback_transports or [],
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier=target.identifier,
        target_address=target.address,
        status="started",
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    job = DiscoveryJobRepository(session).create(
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        requested_capabilities={
            "collector_name": collector_name,
            "capabilities": [],
        },
    )
    session.commit()
    return job


def _job_legacy(
    session: Session,
    *,
    collector_name: str = "raw",
    enabled: bool = True,
) -> DiscoveryJobRecord:
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="legacy-01",
        address="10.0.0.99",
        enabled=enabled,
        credential_reference="credential:fake",
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier=target.identifier,
        target_address=target.address,
        status="started",
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    job = DiscoveryJobRepository(session).create(
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        requested_capabilities={"collector_name": collector_name},
    )
    session.commit()
    return job


def _register_all_transports(
    registry: CollectorRegistry,
    *,
    ssh_cls: type[BaseCollector] = SshSuccessCollector,
    telnet_cls: type[BaseCollector] = TelnetSuccessCollector,
    https_cls: type[BaseCollector] = HttpsSuccessCollector,
) -> None:
    registry.register(
        ssh_cls(name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH}))
    )
    registry.register(
        telnet_cls(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        https_cls(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )


def test_runtime_policy_ssh_profile_rejects_unsupported_fallbacks() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    target_view = DiscoveryTargetRecordView(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="core-01",
        address="10.0.0.1",
        enabled=True,
        metadata={
            "credential_profile_id": str(profile.id),
            "transport_name": "ssh",
            "allowed_fallback_transports": ["telnet", "https", "http", "snmp"],
            "allow_insecure_telnet": True,
            "allow_insecure_http": True,
        },
    )

    service = DiscoveryExecutionService(session, CollectorRegistry())
    policy = service._resolve_transport_policy(target_view)

    assert policy.transport_names == ["ssh"]
    assert "telnet" not in policy.transport_names
    assert "https" not in policy.transport_names
    assert "http" not in policy.transport_names
    assert "snmp" not in policy.transport_names


@pytest.mark.anyio
async def test_A_ssh_success_no_fallback_single_transport() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshSuccessCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport == "ssh"
    attempts = session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].transport == "ssh"
    assert attempts[0].attempt_order == 1
    assert attempts[0].result == "success"


@pytest.mark.anyio
async def test_cisco_nested_raw_payload_is_parsed_before_identity_validation() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    job = _job_with_profile(session, profile=profile, collector_name="cisco-raw")
    registry = CollectorRegistry()
    registry.register(CiscoRawPayloadCollector())

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport == "ssh"
    assert result.failure_code is None
    attempt = session.execute(select(DiscoveryTransportAttemptRecord)).scalar_one()
    assert attempt.result == "success"


@pytest.mark.anyio
async def test_cisco_empty_cli_output_remains_no_identity_failure() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    job = _job_with_profile(session, profile=profile, collector_name="cisco-raw")
    registry = CollectorRegistry()
    registry.register(
        CiscoRawPayloadCollector(
            payload={
                "target": {
                    "identifier": "core-01",
                    "address": "10.0.0.1",
                    "metadata": {},
                },
                "platform_family": "catalyst-2960",
                "parser_family": "ios",
                "transport": "ssh",
                "commands": {"show version": "", "show inventory": ""},
            }
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == DiscoveryFailureCode.DISCOVERY_FAILED.value
    assert outcome.job.failure_message == (
        "Collector did not return device identification data"
    )
    attempt = session.execute(select(DiscoveryTransportAttemptRecord)).scalar_one()
    assert attempt.failure_code == DiscoveryFailureCode.DISCOVERY_FAILED.value


@pytest.mark.anyio
async def test_cisco_malformed_cli_output_remains_no_identity_failure() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    job = _job_with_profile(session, profile=profile, collector_name="cisco-raw")
    registry = CollectorRegistry()
    registry.register(
        CiscoRawPayloadCollector(
            payload={
                "target": {
                    "identifier": "core-01",
                    "address": "10.0.0.1",
                    "metadata": {},
                },
                "platform_family": "catalyst-2960",
                "parser_family": "ios",
                "transport": "ssh",
                "commands": {
                    "show version": "not Cisco output",
                    "show inventory": "invalid inventory output",
                },
            }
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == DiscoveryFailureCode.DISCOVERY_FAILED.value
    attempt = session.execute(select(DiscoveryTransportAttemptRecord)).scalar_one()
    assert attempt.failure_message == (
        "Collector did not return device identification data"
    )


@pytest.mark.anyio
async def test_cisco_command_exception_keeps_exception_failure_path() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    job = _job_with_profile(session, profile=profile, collector_name="cisco-raw")
    registry = CollectorRegistry()
    registry.register(
        CiscoRawPayloadCollector(error=TimeoutError("SSH command timed out"))
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == DiscoveryFailureCode.CONNECTION_FAILED.value
    assert (
        outcome.job.failure_message
        == "Host was unreachable for all configured transports."
    )
    attempt = session.execute(select(DiscoveryTransportAttemptRecord)).scalar_one()
    assert attempt.failure_code == DiscoveryFailureCode.CONNECTION_TIMEOUT.value
    assert attempt.failure_message == "SSH command timed out"


@pytest.mark.anyio
async def test_B_ssh_fails_then_telnet_succeeds_fallback() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshFailReachableCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport == "telnet"
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    assert len(attempts) == 2
    assert attempts[0].transport == "ssh"
    assert attempts[0].attempt_order == 1
    assert attempts[0].result == "failed"
    assert attempts[1].transport == "telnet"
    assert attempts[1].attempt_order == 2
    assert attempts[1].result == "success"


@pytest.mark.anyio
async def test_C_ssh_fails_telnet_fails_then_https_succeeds_three_step_fallback() -> (
    None
):
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet", "https"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshFailReachableCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsSuccessCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport == "https"
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    assert len(attempts) == 3
    assert attempts[0].transport == "ssh" and attempts[0].attempt_order == 1
    assert attempts[0].result == "failed"
    assert attempts[1].transport == "telnet" and attempts[1].attempt_order == 2
    assert attempts[1].result == "failed"
    assert attempts[2].transport == "https" and attempts[2].attempt_order == 3
    assert attempts[2].result == "success"


@pytest.mark.anyio
async def test_D_all_transports_fail_distinguish_reachable_vs_auth_failure() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet", "https"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshAuthFailCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsFailCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.AUTHENTICATION_FAILED.value
    assert result.selected_transport is None
    assert result.failure_code == DiscoveryFailureCode.AUTHENTICATION_FAILED.value
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    assert len(attempts) == 3
    assert attempts[0].failure_code == DiscoveryFailureCode.AUTHENTICATION_FAILED.value
    assert "invalid credentials" in attempts[0].failure_message


@pytest.mark.anyio
async def test_transport_attempt_records_preserve_failure_message_without_secrets() -> (
    None
):
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshAuthFailCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )

    await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda attempt: attempt.attempt_order,
    )
    assert len(attempts) == 2
    assert attempts[0].failure_code == DiscoveryFailureCode.AUTHENTICATION_FAILED.value
    assert attempts[0].failure_message is not None
    assert "invalid credentials" in attempts[0].failure_message
    assert "secret" not in attempts[0].failure_message.lower()


@pytest.mark.anyio
async def test_D2_ssh_telnet_https_fail_then_http_succeeds() -> None:
    session = _session()
    profile = _credential_profile(
        session, transport_types=["ssh", "telnet", "https", "http"]
    )
    job = _job_with_profile(session, profile=profile)
    target = session.get(DiscoveryTargetRecord, job.target_id)
    assert target is not None
    target.metadata_json = {"allow_insecure_http": True}
    session.commit()
    registry = CollectorRegistry()
    registry.register(
        SshFailReachableCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsFailCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )
    registry.register(
        HttpSuccessCollector(
            name="http-cisco", capabilities=frozenset({CollectorCapability.HTTP})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value, (
        outcome.job.failure_code,
        outcome.job.failure_message,
    )
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport == "http"
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda attempt: attempt.attempt_order,
    )
    assert [attempt.transport for attempt in attempts] == [
        "ssh",
        "telnet",
        "https",
        "http",
    ]
    assert [attempt.result for attempt in attempts] == [
        "failed",
        "failed",
        "failed",
        "success",
    ]


@pytest.mark.anyio
async def test_E_host_unreachable_all_timeout_no_management() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet", "https"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshTimeoutCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        SshTimeoutCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        SshTimeoutCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.UNREACHABLE.value
    assert result.selected_transport is None
    assert result.failure_code == DiscoveryFailureCode.CONNECTION_FAILED.value
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    assert len(attempts) == 3
    for a in attempts:
        assert a.result == "failed"


@pytest.mark.anyio
async def test_E_generic_discovery_failure_is_reachable_no_management() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet", "https"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        GenericDiscoveryFailCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        GenericDiscoveryFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        GenericDiscoveryFailCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
    assert result.failure_code == DiscoveryFailureCode.DISCOVERY_FAILED.value


@pytest.mark.anyio
async def test_F_ssh_auth_fail_continue_chain_telnet_succeeds() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshAuthFailCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport == "telnet"
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    assert len(attempts) == 2
    assert attempts[0].transport == "ssh"
    assert attempts[0].attempt_order == 1
    assert attempts[0].result == "failed"
    assert attempts[0].failure_code == DiscoveryFailureCode.AUTHENTICATION_FAILED.value
    assert attempts[1].transport == "telnet"
    assert attempts[1].attempt_order == 2
    assert attempts[1].result == "success"


@pytest.mark.anyio
async def test_G_snmp_credential_ssh_transport_unsupported_credential_code() -> None:
    session = _session()
    profile = _credential_profile(
        session,
        transport_types=["ssh", "telnet", "https"],
        credential_type="snmp_v2c",
    )
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshSuccessCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsSuccessCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )
    registry.register(
        SnmpCollector(
            name="snmp-cisco", capabilities=frozenset({CollectorCapability.SNMP})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    attempts = session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all()
    unsupported = [
        a
        for a in attempts
        if a.failure_code == DiscoveryFailureCode.UNSUPPORTED_CREDENTIAL.value
    ]
    assert len(unsupported) >= 1
    transport_names_unsupported = {a.transport for a in unsupported}
    assert (
        "ssh" in transport_names_unsupported
        or "telnet" in transport_names_unsupported
        or "https" in transport_names_unsupported
    )


@pytest.mark.anyio
async def test_H_allow_insecure_telnet_false_skips_telnet_in_chain() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet", "https"])
    job = _job_with_profile(session, profile=profile, allow_insecure_telnet=False)
    registry = CollectorRegistry()
    registry.register(
        SshFailReachableCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsSuccessCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    attempts = session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all()
    transport_names = {a.transport for a in attempts}
    assert "telnet" not in transport_names
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.selected_transport == "https"


@pytest.mark.anyio
async def test_I_target_fallback_not_supported_by_profile_is_skipped() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh"])
    job = _job_with_profile(
        session,
        profile=profile,
        fallback_transports=["telnet", "https"],
        allow_insecure_telnet=True,
    )
    registry = CollectorRegistry()
    registry.register(
        SshAuthFailCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsSuccessCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.AUTHENTICATION_FAILED.value
    assert result.selected_transport is None
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    assert [attempt.transport for attempt in attempts] == ["ssh"]
    assert attempts[0].result == "failed"
    assert attempts[0].failure_code == DiscoveryFailureCode.AUTHENTICATION_FAILED.value


@pytest.mark.anyio
async def test_J_legacy_ssh_only_profile_no_profile_defaults_to_ssh() -> None:
    session = _session()
    job = _job_legacy(session, collector_name="legacy-ssh")
    registry = CollectorRegistry()
    registry.register(
        SshSuccessCollector(
            name="legacy-ssh", capabilities=frozenset({CollectorCapability.SSH})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    assert result.result_state == DiscoveryResultState.DISCOVERED.value
    assert result.selected_transport is not None
    attempts = session.execute(select(DiscoveryTransportAttemptRecord)).all()
    assert len(attempts) == 1


@pytest.mark.anyio
async def test_J_summary_math_counts_add_up_correctly() -> None:
    session = _session()

    scenarios = [
        (SshSuccessCollector, "ssh", DiscoveryResultState.DISCOVERED.value, 1),
        (SshFailReachableCollector, "ssh_fail", None, 3),
    ]
    profiles = []
    jobs = []
    for cls, suffix, expected_state, expected_attempts in scenarios:
        profile = _credential_profile(
            session, transport_types=["ssh", "telnet", "https"]
        )
        profiles.append(profile)
        job = _job_with_profile(
            session,
            profile=profile,
            identifier=f"dev-{suffix}",
            address=f"10.0.1.{len(jobs)+1}",
        )
        jobs.append((job, cls, expected_state, expected_attempts))

    registry = CollectorRegistry()
    registry.register(
        TelnetFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsFailCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    for idx, (job, cls, expected_state, expected_attempts) in enumerate(jobs):
        if idx == 0:
            registry.register(
                cls(
                    name="ssh-cisco",
                    capabilities=frozenset({CollectorCapability.SSH}),
                )
            )
        else:
            # Overwrite SSH collector with failing one for subsequent jobs
            pass

    registry2 = CollectorRegistry()
    registry2.register(
        SshSuccessCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry2.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry2.register(
        HttpsSuccessCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome1 = await DiscoveryExecutionService(session, registry2).execute(
        tenant_id="tenant-a", job_id=jobs[0][0].id
    )
    assert outcome1.job.state == DiscoveryJobStatus.SUCCEEDED.value

    registry3 = CollectorRegistry()
    registry3.register(
        SshFailReachableCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry3.register(
        TelnetFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry3.register(
        HttpsFailCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )

    outcome2 = await DiscoveryExecutionService(session, registry3).execute(
        tenant_id="tenant-a", job_id=jobs[1][0].id
    )
    assert outcome2.job.state == DiscoveryJobStatus.FAILED.value

    results = session.execute(select(DiscoveryDeviceResultRecord)).scalars().all()
    assert len(results) == 2
    discovered = sum(
        1 for r in results if r.result_state == DiscoveryResultState.DISCOVERED.value
    )
    reachable_no_mgmt = sum(
        1
        for r in results
        if r.result_state == DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
    )
    total_attempts = len(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all()
    )
    assert discovered + reachable_no_mgmt == len(results)
    assert total_attempts == 1 + 3


@pytest.mark.anyio
async def test_K_attempt_order_sequence_is_1_to_N_strictly_increasing() -> None:
    session = _session()
    profile = _credential_profile(
        session, transport_types=["ssh", "telnet", "https", "http"]
    )
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()
    registry.register(
        SshFailReachableCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetFailCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )
    registry.register(
        HttpsFailCollector(
            name="https-cisco", capabilities=frozenset({CollectorCapability.HTTPS})
        )
    )
    registry.register(
        SshSuccessCollector(
            name="http-cisco", capabilities=frozenset({CollectorCapability.HTTP})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    attempts = sorted(
        session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all(),
        key=lambda a: a.attempt_order,
    )
    for idx, attempt in enumerate(attempts, start=1):
        assert attempt.attempt_order == idx, (
            f"Expected attempt_order={idx} for {attempt.transport}, "
            f"got {attempt.attempt_order}"
        )
    orders = [a.attempt_order for a in attempts]
    assert orders == list(range(1, len(attempts) + 1))


@pytest.mark.anyio
async def test_L_no_secrets_password_or_secret_in_any_record_or_payload() -> None:
    session = _session()
    profile = _credential_profile(session, transport_types=["ssh", "telnet"])
    job = _job_with_profile(session, profile=profile)
    registry = CollectorRegistry()

    class SshLeakAttemptCollector(BaseCollector):
        async def health_check(self, context: CollectorContext) -> None:
            await asyncio.sleep(0)

        async def discover(self, context: CollectorContext):
            return ()

        async def collect(self, context: CollectorContext, *, discovered_targets):
            return {
                "hostname": context.target.identifier,
                "transport": "ssh",
                "platform_family": "cisco-iosxe",
                "facts": {
                    "serial": "SERIAL-1",
                    "admin_password": "SuperSecret123!",
                    "enable_secret": "mySecretEnablePass",
                    "api_key_token": "tok_abc_secret_value",
                },
                "raw_output": "username admin password SecretP@ss line",
            }

        async def normalize(self, context, raw_payload, *, discovered_targets):
            raise AssertionError("Must not normalize")

        async def close(self) -> None:
            return None

    registry.register(
        SshLeakAttemptCollector(
            name="ssh-cisco", capabilities=frozenset({CollectorCapability.SSH})
        )
    )
    registry.register(
        TelnetSuccessCollector(
            name="telnet-cisco", capabilities=frozenset({CollectorCapability.TELNET})
        )
    )

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    result = session.execute(select(DiscoveryDeviceResultRecord)).scalar_one()
    attempts = session.execute(select(DiscoveryTransportAttemptRecord)).scalars().all()
    evidence_records = session.execute(select(DiscoveryEvidenceRecord)).scalars().all()

    all_strings: list[str] = []
    for field_name in [
        "hostname",
        "vendor",
        "platform",
        "state",
        "result_state",
        "selected_transport",
        "failure_code",
        "failure_message",
    ]:
        val = getattr(result, field_name, None)
        if val is not None:
            all_strings.append(str(val))

    for attempt in attempts:
        for field_name in [
            "transport",
            "result",
            "failure_code",
        ]:
            val = getattr(attempt, field_name, None)
            if val is not None:
                all_strings.append(str(val))

    for ev in evidence_records:
        all_strings.append(str(ev.payload).lower())
        all_strings.append(str(ev.evidence_type).lower())
        all_strings.append(str(ev.source).lower())

    combined = " ".join(all_strings).lower()
    assert "supersecret123" not in combined
    assert "mysecretenablepass" not in combined
    assert "secretp@ss" not in combined
    assert "tok_abc_secret_value" not in combined
