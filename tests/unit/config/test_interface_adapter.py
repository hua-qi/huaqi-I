import pytest
from huaqi_src.config.adapters.interface_base import InterfaceAdapter


def test_interface_adapter_is_abstract():
    with pytest.raises(TypeError):
        InterfaceAdapter()


def test_interface_adapter_methods():
    methods = ["send_message", "send_question", "display_progress"]
    for m in methods:
        assert hasattr(InterfaceAdapter, m)
