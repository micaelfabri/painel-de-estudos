"""Testes do endurecimento da auditoria de segurança (docs/security-audit)."""


def test_rejects_unknown_host(client):
    # DNS rebinding: um domínio externo apontando para 127.0.0.1 chega com outro Host
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/health", headers={"Host": "localhost:8000"}).status_code == 200


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_llm_base_url_only_http(client):
    for bad in ["file:///etc/passwd", "ftp://x/v1", "http://", "javascript:alert(1)"]:
        assert client.put("/api/settings/llm_base_url", json={"value": bad}).status_code == 422, bad
    ok = client.put("/api/settings/llm_base_url", json={"value": "http://host.docker.internal:1234/v1"})
    assert ok.status_code == 200


def test_llm_timeout_setting_bounds(client):
    assert client.get("/api/settings").json()["values"]["llm_timeout_seconds"] == 900
    assert client.put("/api/settings/llm_timeout_seconds", json={"value": 10}).status_code == 422
    assert client.put("/api/settings/llm_timeout_seconds", json={"value": 1200}).status_code == 200


def test_blocks_cross_site_writes(client):
    # POST simples vindo de outro site (CSRF) é recusado; a própria página e ferramentas locais passam
    url = "/api/learning/checklist/plan"
    assert client.post(url, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post(url, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post(url, headers={"Sec-Fetch-Site": "same-site"}).status_code == 403
    assert client.post(url, headers={"Sec-Fetch-Site": "same-origin", "Origin": "http://localhost:8000"}).status_code == 200
    assert client.post(url, headers={"Origin": "http://localhost:5173"}).status_code == 200
    assert client.post(url).status_code == 200
    # Leitura de outro site continua permitida (a CSP e a ausência de CORS já protegem a resposta)
    assert client.get("/api/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200
