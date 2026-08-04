from backend.app.core.application import ApplicationContainer, create_application
from backend.app.core.constants import APP_NAME


def test_application_factory_exposes_container() -> None:
    app = create_application()

    container = app.state.container

    assert isinstance(container, ApplicationContainer)
    assert app.title == APP_NAME
    assert container.metadata.name == APP_NAME
