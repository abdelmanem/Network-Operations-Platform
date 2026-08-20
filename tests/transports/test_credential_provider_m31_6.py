from backend.app.transports.credentials import (
    CredentialReference,
    EnvironmentCredentialProvider,
    SNMPv2cCredentials,
    UsernamePasswordCredentials,
)


def test_environment_provider_resolves_ssh_without_exposing_secret(monkeypatch) -> None:
    monkeypatch.setenv("NOP_CREDENTIAL_CISCO_PROD_SSH", "super-secret")
    monkeypatch.setenv("NOP_CREDENTIAL_CISCO_PROD_USERNAME", "netops")

    credentials = EnvironmentCredentialProvider().resolve_reference(
        CredentialReference(
            credential_id="cisco-prod",
            transport="ssh",
            tenant_id="tenant-a",
        )
    )

    assert isinstance(credentials, UsernamePasswordCredentials)
    assert credentials.username == "netops"
    assert credentials.password == "super-secret"
    assert (
        "super-secret"
        not in CredentialReference("cisco-prod", "ssh", "tenant-a").as_dict().values()
    )


def test_environment_provider_resolves_snmpv2c_community_at_execution_time(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NOP_CREDENTIAL_SNMP_PROD_SNMP", "community-secret")

    credentials = EnvironmentCredentialProvider().resolve_reference(
        CredentialReference(
            credential_id="snmp-prod",
            transport="snmp",
            tenant_id="tenant-a",
        )
    )

    assert isinstance(credentials, SNMPv2cCredentials)
    assert credentials.community == "community-secret"
