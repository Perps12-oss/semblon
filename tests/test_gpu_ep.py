"""GPU / ORT execution-provider productization honesty."""

from __future__ import annotations

from unittest.mock import patch

from semblon.engine import (
    GPU_EP_NAMES,
    format_execution_status_lines,
    gpu_product_status,
    product_prefer_gpu,
    select_execution_provider,
)


def test_cpu_only_never_claims_gpu():
    with patch(
        "semblon.engine.onnx_providers",
        return_value=["CPUExecutionProvider"],
    ):
        rec = select_execution_provider(prefer_gpu=True)
        assert product_prefer_gpu() is False
        st = gpu_product_status()
    assert rec["gpu"] is False
    assert rec["device"] == "cpu"
    assert rec["chosen"] == "CPUExecutionProvider"
    assert st["prefer_gpu"] is False
    assert st["product_path"] == "cpu"
    assert "Do not claim GPU" in st["copy"]


def test_azure_is_not_gpu():
    providers = ["AzureExecutionProvider", "CPUExecutionProvider"]
    with patch("semblon.engine.onnx_providers", return_value=providers):
        rec = select_execution_provider(prefer_gpu=True)
        st = gpu_product_status()
        lines = format_execution_status_lines()
    assert rec["gpu"] is False
    assert rec["device"] == "cpu"
    assert rec["chosen"] == "CPUExecutionProvider"
    assert "AzureExecutionProvider" in rec["azure_listed"]
    assert rec["gpu_eps"] == []
    assert "not GPU" in st["copy"]
    text = "\n".join(lines)
    assert "not GPU" in text
    assert "Azure" in text
    assert "gpu=False" in text


def test_cuda_listed_product_prefers_gpu():
    with patch(
        "semblon.engine.onnx_providers",
        return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
    ):
        rec = select_execution_provider(prefer_gpu=True)
        assert product_prefer_gpu() is True
        st = gpu_product_status()
    assert rec["gpu"] is True
    assert rec["device"] == "gpu"
    assert rec["chosen"] == "CUDAExecutionProvider"
    assert st["product_path"] == "prefer_gpu"
    assert "GPU EP listed" in st["copy"]


def test_prefer_gpu_false_stays_cpu_even_if_cuda_listed():
    with patch(
        "semblon.engine.onnx_providers",
        return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
    ):
        rec = select_execution_provider(prefer_gpu=False)
    assert rec["gpu"] is False
    assert rec["chosen"] == "CPUExecutionProvider"
    assert rec["device"] == "cpu"


def test_dml_and_tensorrt_are_gpu_eps():
    assert "DmlExecutionProvider" in GPU_EP_NAMES
    assert "TensorrtExecutionProvider" in GPU_EP_NAMES
    assert "AzureExecutionProvider" not in GPU_EP_NAMES
    with patch(
        "semblon.engine.onnx_providers",
        return_value=["DmlExecutionProvider", "CPUExecutionProvider"],
    ):
        rec = select_execution_provider(prefer_gpu=True)
    assert rec["chosen"] == "DmlExecutionProvider"
    assert rec["gpu"] is True


def test_azure_only_falls_back_without_claiming_gpu():
    with patch(
        "semblon.engine.onnx_providers",
        return_value=["AzureExecutionProvider"],
    ):
        rec = select_execution_provider(prefer_gpu=True)
    assert rec["gpu"] is False
    # No CPU listed: may keep Azure as chosen, but never gpu=True.
    assert rec["chosen"] == "AzureExecutionProvider"
    assert rec["device"] == "cpu"


def test_settings_lines_include_arch_execution():
    with patch(
        "semblon.engine.onnx_providers",
        return_value=["CPUExecutionProvider"],
    ):
        lines = format_execution_status_lines()
    text = "\n".join(lines)
    assert "FaceKit" in text
    assert "arch=" in text
    assert "execution=" in text
    assert "CPU" in text


def test_home_settings_uses_execution_status_lines():
    import inspect

    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._show_settings)
    assert "format_execution_status_lines" in src
    assert "FaceKit CPU (not claimed GPU)" not in src


def test_home_ingest_passes_product_prefer_gpu():
    import inspect

    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._start_process)
    assert "resolve_home_prefer_gpu" in src or "product_prefer_gpu" in src
    assert "prefer_gpu=" in src


def test_job_engine_accepts_prefer_gpu():
    import inspect

    from semblon.jobs import JobEngine

    sig = inspect.signature(JobEngine.submit_ingest)
    assert "prefer_gpu" in sig.parameters
