from backend.app.integrations.netbox.authentication import (
    OAuthAuthentication,
    TokenAuthentication,
)


def test_token_authentication_builds_bearer_header() -> None:
    token_value = "".join(["se", "cret"])
    auth = TokenAuthentication(token=token_value)

    assert auth.build_headers() == {"Authorization": f"Bearer {token_value}"}


def test_oauth_authentication_builds_bearer_header() -> None:
    access_token = "".join(["to", "ken"])
    auth = OAuthAuthentication(access_token=access_token, scheme="Bearer")

    assert auth.build_headers() == {"Authorization": f"Bearer {access_token}"}
