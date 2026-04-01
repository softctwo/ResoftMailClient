import importlib


def test_eas_client_package_is_importable_from_src_pythonpath() -> None:
    config = importlib.import_module("eas_client.config")
    transport = importlib.import_module("eas_client.transport")
    commands = importlib.import_module("eas_client.eas.commands")

    assert config.ClientConfig is not None
    assert transport.EasTransport is not None
    assert commands.build_sync_request is not None
