"""
全链路 API 测试套件
运行：cd ecommerce_ai_chat/backend && python -m pytest test_api.py -v
"""
import random, string, pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


# ── 工具函数 ────────────────────────────────────────────────────

def _rand(n=8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))

def _register() -> tuple[str, str, str]:
    """注册随机用户，返回 (username, password, token)"""
    u, p = f"t_{_rand()}", f"pw_{_rand()}"
    r = client.post("/api/auth/register", json={"username": u, "password": p})
    assert r.status_code == 200, f"测试账号注册失败: {r.text}"
    return u, p, r.json()["token"]

def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ════════════════════════════════════════════════════════════════
# 1. 认证模块
# ════════════════════════════════════════════════════════════════

class TestAuth:

    def test_register_ok(self):
        u, p = f"t_{_rand()}", f"pw_{_rand()}"
        r = client.post("/api/auth/register", json={"username": u, "password": p})
        assert r.status_code == 200
        assert "token" in r.json()
        assert r.json()["username"] == u

    def test_register_duplicate(self):
        u, p = f"t_{_rand()}", f"pw_{_rand()}"
        client.post("/api/auth/register", json={"username": u, "password": p})
        r = client.post("/api/auth/register", json={"username": u, "password": p})
        assert r.status_code == 400
        assert "已存在" in r.json().get("detail", "")

    def test_register_username_too_short(self):
        r = client.post("/api/auth/register", json={"username": "a", "password": "pass1234"})
        assert r.status_code == 400

    def test_register_password_too_short(self):
        r = client.post("/api/auth/register", json={"username": f"t_{_rand()}", "password": "abc"})
        assert r.status_code == 400

    def test_login_ok(self):
        u, p, _ = _register()
        r = client.post("/api/auth/login", json={"username": u, "password": p})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_wrong_password(self):
        u, p, _ = _register()
        r = client.post("/api/auth/login", json={"username": u, "password": "wrongpass"})
        assert r.status_code == 400

    def test_login_nonexistent_user(self):
        r = client.post("/api/auth/login", json={"username": f"ghost_{_rand()}", "password": "pass1234"})
        assert r.status_code == 400

    def test_invalid_token_rejected(self):
        r = client.get("/api/sessions", headers={"Authorization": "Bearer fake.token.here"})
        assert r.status_code == 401

    def test_missing_token_rejected(self):
        r = client.get("/api/sessions")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════
# 2. 会话管理模块
# ════════════════════════════════════════════════════════════════

class TestSessions:

    @pytest.fixture(autouse=True)
    def setup(self):
        _, _, tok = _register()
        self.h = _hdrs(tok)

    def test_create_session(self):
        r = client.post("/api/sessions", headers=self.h)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data and "title" in data and "updated_at" in data

    def test_list_sessions(self):
        client.post("/api/sessions", headers=self.h)
        r = client.get("/api/sessions", headers=self.h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_get_session(self):
        sid = client.post("/api/sessions", headers=self.h).json()["id"]
        r = client.get(f"/api/sessions/{sid}", headers=self.h)
        assert r.status_code == 200
        assert r.json()["id"] == sid
        assert "messages" in r.json()

    def test_update_session_title(self):
        sid = client.post("/api/sessions", headers=self.h).json()["id"]
        r = client.put(f"/api/sessions/{sid}",
                       json={"title": "测试标题", "messages": []},
                       headers=self.h)
        assert r.status_code == 200
        # 标题确实更新
        r2 = client.get("/api/sessions", headers=self.h)
        titles = [s["title"] for s in r2.json()]
        assert "测试标题" in titles

    def test_update_session_messages(self):
        sid = client.post("/api/sessions", headers=self.h).json()["id"]
        msgs = [{"role": "user", "content": "hello"}]
        client.put(f"/api/sessions/{sid}", json={"messages": msgs}, headers=self.h)
        r = client.get(f"/api/sessions/{sid}", headers=self.h)
        assert r.json()["messages"][0]["content"] == "hello"

    def test_delete_session(self):
        sid = client.post("/api/sessions", headers=self.h).json()["id"]
        r = client.delete(f"/api/sessions/{sid}", headers=self.h)
        assert r.status_code == 200
        r2 = client.get(f"/api/sessions/{sid}", headers=self.h)
        assert r2.status_code == 404

    def test_get_nonexistent_session(self):
        r = client.get("/api/sessions/99999999", headers=self.h)
        assert r.status_code == 404

    def test_cross_user_get_blocked(self):
        sid = client.post("/api/sessions", headers=self.h).json()["id"]
        _, _, tok2 = _register()
        r = client.get(f"/api/sessions/{sid}", headers=_hdrs(tok2))
        assert r.status_code == 404

    def test_cross_user_delete_blocked(self):
        sid = client.post("/api/sessions", headers=self.h).json()["id"]
        _, _, tok2 = _register()
        r = client.delete(f"/api/sessions/{sid}", headers=_hdrs(tok2))
        assert r.status_code == 404

    def test_session_list_isolated_per_user(self):
        # User1 创建 2 个会话
        client.post("/api/sessions", headers=self.h)
        client.post("/api/sessions", headers=self.h)
        # User2 创建 1 个会话
        _, _, tok2 = _register()
        client.post("/api/sessions", headers=_hdrs(tok2))
        # User2 的列表不应包含 User1 的会话
        r = client.get("/api/sessions", headers=_hdrs(tok2))
        assert len(r.json()) == 1


# ════════════════════════════════════════════════════════════════
# 3. 端点可达性（无需 API Key）
# ════════════════════════════════════════════════════════════════

class TestEndpointAvailability:
    """
    验证端点存在、鉴权生效、参数校验生效。
    不调用外部 AI API，仅验证路由和中间件层。
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        _, _, tok = _register()
        self.h = _hdrs(tok)

    def test_analyze_rejects_missing_text(self):
        r = client.post("/api/analyze", headers=self.h)
        # 422 = 参数缺失，端点存在且鉴权通过
        assert r.status_code == 422, f"analyze 应返回 422 (缺少 text 字段)，实际: {r.status_code}"

    def test_analyze_is_public_endpoint(self):
        # analyze 无需鉴权；缺 text 字段时 FastAPI 返回 422
        r = client.post("/api/analyze")
        assert r.status_code == 422

    def test_generate_rejects_empty_body(self):
        r = client.post("/api/generate", json={}, headers=self.h)
        assert r.status_code in (422, 400)

    def test_generate_is_public_endpoint(self):
        # generate 无需鉴权；空 body 时 pydantic 返回 422
        r = client.post("/api/generate", json={})
        assert r.status_code in (422, 400)

    def test_combine_rejects_empty_body(self):
        r = client.post("/api/combine", json={}, headers=self.h)
        assert r.status_code in (422, 400)

    def test_video_analyze_rejects_missing_file(self):
        r = client.post("/api/video/analyze", headers=self.h)
        assert r.status_code == 422

    def test_video_analyze_requires_auth(self):
        r = client.post("/api/video/analyze")
        assert r.status_code == 401

    def test_video_process_rejects_missing_form(self):
        r = client.post("/api/video/process", headers=self.h)
        assert r.status_code == 422

    def test_video_process_requires_auth(self):
        r = client.post("/api/video/process")
        assert r.status_code == 401

    def test_generate_invalid_output_type(self):
        r = client.post("/api/generate",
                        json={"context": {}, "output_type": "invalid_type"},
                        headers=self.h)
        # 500 = 端点通了但 output_type 无效；422 = pydantic 拦截
        assert r.status_code in (400, 422, 500)

    def test_generate_deepseek_model_accepted(self):
        """DeepSeek V4 模型参数能被接受（不会被 pydantic 拒绝）"""
        r = client.post("/api/generate",
                        json={"context": {}, "output_type": "text", "model": "deepseek"},
                        headers=self.h)
        # 500 = 模型参数合法，失败来自 AI API 调用（无 key）
        # 422 = 意外的参数拒绝（这是 bug）
        assert r.status_code != 422, "DeepSeek 模型参数不应被 pydantic 拒绝"

    # ── Pipeline 管道端点 ───────────────────────────────────────

    def test_pipeline_upload_requires_auth(self):
        r = client.post("/api/pipeline/upload")
        assert r.status_code == 401

    def test_pipeline_upload_rejects_missing_file(self):
        r = client.post("/api/pipeline/upload", headers=self.h)
        assert r.status_code == 422

    def test_pipeline_job_requires_auth(self):
        r = client.get("/api/pipeline/job/nonexistent-id")
        assert r.status_code == 401

    def test_pipeline_job_404_for_unknown_id(self):
        r = client.get("/api/pipeline/job/00000000-0000-0000-0000-000000000000", headers=self.h)
        assert r.status_code == 404

    def test_pipeline_download_requires_auth(self):
        r = client.get("/api/pipeline/download/nonexistent-id")
        assert r.status_code == 401

    def test_pipeline_download_404_for_unknown_id(self):
        r = client.get("/api/pipeline/download/00000000-0000-0000-0000-000000000000", headers=self.h)
        assert r.status_code == 404
