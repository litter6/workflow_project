"""端到端流水线测试脚本"""
import requests, json, time, os, tempfile

BASE = "http://localhost:8001"

# 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username": "testpipeline", "password": "test1234567"})
token = r.json()["token"]
print(f"登录成功，Token: {token[:20]}...")
hdrs = {"Authorization": f"Bearer {token}"}

# 上传测试视频
video_path = os.path.join(tempfile.gettempdir(), "test_video.mp4")
print(f"上传视频: {video_path} ({os.path.getsize(video_path)//1024} KB)")
with open(video_path, "rb") as f:
    r = requests.post(f"{BASE}/api/pipeline/upload", headers=hdrs,
                      files={"video": ("test_video.mp4", f, "video/mp4")})

print(f"上传响应: {r.status_code}")
data = r.json()
print(json.dumps(data, ensure_ascii=False, indent=2))
job_id = data.get("job_id", "")

# 轮询状态（最多 120 秒）
print(f"\n开始轮询任务 {job_id}...")
for i in range(60):
    time.sleep(2)
    r2 = requests.get(f"{BASE}/api/pipeline/job/{job_id}", headers=hdrs)
    d = r2.json()
    status   = d.get("status", "")
    progress = d.get("progress", 0)
    stage    = d.get("stage", "")[:40]
    print(f"  [{i*2:3d}s] {status:<12} {progress:3d}%  {stage}")
    if status in ("completed", "failed"):
        print(f"\n=== 最终结果: {status} ===")
        if d.get("error_msg"):
            print(f"错误信息: {d['error_msg']}")
        if d.get("marketing_copy"):
            print(f"营销文案片段: {d['marketing_copy'][:100]}...")
        if d.get("transcript"):
            print(f"字幕片段: {d['transcript'][:80]}...")
        break
else:
    print("超时，任务仍在运行中")
