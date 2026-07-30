import httpx
import pytest

from techgrowth_connector.client import diagnose_server


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_diagnostic_classifies_alibaba_icp_interception() -> None:
    diagnostic = diagnose_server(
        "https://growth.example.com",
        http=client_for(
            lambda _request: httpx.Response(
                403,
                text="Non-compliance ICP Filing",
                headers={"Server": "Beaver"},
            )
        ),
    )

    assert diagnostic.code == "icp_blocked"
    assert diagnostic.ok is False
    assert "备案" in diagnostic.message


@pytest.mark.parametrize("detail", ["SSL unexpected EOF", "connection reset by peer"])
def test_diagnostic_classifies_tls_reset(detail: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(detail, request=request)

    diagnostic = diagnose_server("https://growth.example.com", http=client_for(handler))

    assert diagnostic.code == "tls_connection_failed"
    assert "TLS" in diagnostic.message


def test_diagnostic_accepts_healthy_server() -> None:
    diagnostic = diagnose_server(
        "https://growth.example.com",
        http=client_for(lambda _request: httpx.Response(200, json={"status": "ok"})),
    )

    assert diagnostic.code == "ok"
    assert diagnostic.ok is True
