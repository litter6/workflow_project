import os
import openai

# 设置代理
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

# 设置 API Key
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

try:
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "测试通过Clash代理"}],
        timeout=10
    )
    print("调用成功:", response.choices[0].message.content)
except Exception as e:
    print("调用失败:", e)