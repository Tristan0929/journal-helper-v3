# -*- coding: utf-8 -*-
"""
外刊阅读助手 v3
- 纯转发服务器：不存储、不记录任何 API Key，Key 由每个用户自己在浏览器填写并随请求带上。
- 支持多服务商（DeepSeek 默认，可自选 OpenAI / Kimi / 智谱 / 自定义）。
- /analyze 和 /chat 流式输出；/exercises 生成阅读练习题（JSON）。
"""
import os
import json
import re
from flask import Flask, render_template, request, Response, jsonify
from openai import OpenAI

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ---------------------------------------------------------------------------
# 笔记生成提示词（在 v2 基础上：保留五板块原样；只新增“整理版面”“不重复罗列句子”“技巧用三级标题”几条）
# ---------------------------------------------------------------------------
ANALYZE_SYSTEM_PROMPT = """分析下面的英文文章，做成一份个人学习笔记。只输出最终结果，不要任何开场白或结语。

### 关于原文清理（重要）
用户复制的原文往往很乱，因为外刊多为分栏排版。请在“文章展示”板块先把版面理顺：合并被分栏拆散、交错拼接的句子；修复行尾连字符断词（如 "infor-\\nmation" → "information"）；删除混入正文的页眉、页脚、页码、栏目名、图注等杂质；按语义重新分段。只做版面整理，尽量忠实原文用词，不要改写句子内容。

### 要求概览
- 文章展示 → 脚注解析 → 句子赏析 → 写作手法 → 背诵速查表，五个板块缺一不可。
- 所有板块内容尽量详尽，不要人为限制数量，把文中值得学习的地方都挖掘出来。
- 行文简洁清晰，像自己写给自己的笔记，不要导师口吻。
- 若对某处史实或用法不确定，标注“(存疑，请以教材/原文为准)”。

## 一、文章展示
- 用二级标题“## 文章”开头，然后给出整理后的文章全文。
- 将所有地道、精彩的词汇和词组用 **加粗** 标记，并紧接其后添加脚注标记 [^n]（n从1开始递增）。重复词汇只标注首次出现。
- 用 *斜体* 标记文中特别精彩的句子（不限数量，只要是觉得好就标）。
- 精彩句子只在正文里就地用斜体标注即可；**不要**在文章末尾或任何位置再把这些句子单独罗列成一份清单。

## 二、脚注解析
二级标题“## 📖 词汇词组精析”，按顺序解析每一个脚注，一个不能少。格式：

[^n]: **词/词组** (词性)
核心释义 + 为什么地道。
📖 联动：(具体影视台词或外刊句子，必须完整)
💡 仿写：(完整的英文仿写句)

- 脚注内部使用 <br> 换行。
- 脚注之间空一行。

## 三、句子赏析
二级标题“## 🖋️ 精彩句子赏析”。逐一赏析前面用 *斜体* 标出的每一个句子。每个句子用有序列表的一项，包含三行：
- **原句**：...
- **妙处**：...（结构、修辞、用词、节奏等，简明点出）
- **仿写**：...（模仿其特点写一个完整英文句）

## 四、写作手法分析
二级标题“## ✍️ 写作手法仿写”。选出文中突出的写作技巧，每个技巧的名称用三级标题（### 技巧名称）开头，其下包含：
- **原文呈现**：引用文中句子
- **效用分析**：它为什么好
- **实战仿写**：用不同主题写一个英文段落，真正用上该技巧

## 五、背诵速查表
二级标题“## 📋 背诵速查表”。用表格列出所有加粗词汇/词组，列：表达 | 释义 | 场景。

整份笔记用 Markdown 输出。"""

CHAT_SYSTEM_PROMPT = """你是一位专业的英语语言与写作导师，帮助用户深入理解英文文章。用户可以自由提任何问题，不限于选中的文本。

回答原则：
1. 先给出常规、通用的解释（词义、语法、用法、翻译等），准确简洁。
2. 如果用户选中了某段文本，或问题与正在学习的文章相关，再补充说明它在本文语境中的用法——但仅当这种用法确实有独特、值得一提之处时才补充；常规用法不必强行关联。
3. 不确定的史实或用法要如实说明，不要编造。

回答用中文，简洁、准确、有帮助。"""

EXERCISE_SYSTEM_PROMPT = """你是英语阅读理解出题老师。根据用户给的文章，出 5 道阅读理解选择题，覆盖主旨大意、细节理解、词义猜测、推理判断、作者态度等题型。每题 4 个选项，只有一个正确答案。

严格只输出 JSON，不要任何多余文字、不要用代码块包裹，格式：
{"questions":[{"q":"英文题干","options":["A. ...","B. ...","C. ...","D. ..."],"answer":0,"explanation":"中文解析：为什么这个对、别的错"}]}

题干和选项用英文，explanation 用中文。answer 是正确选项的下标（0-3）。"""


def make_client(api_key, base_url):
    if not base_url:
        base_url = "https://api.deepseek.com"
    return OpenAI(api_key=api_key, base_url=base_url)


def sse_stream(client, model, messages, temperature, max_tokens):
    try:
        stream = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            piece = getattr(chunk.choices[0].delta, "content", None)
            if piece:
                yield "data: " + json.dumps({"delta": piece}, ensure_ascii=False) + "\n\n"
        yield "data: " + json.dumps({"done": True}) + "\n\n"
    except Exception as e:
        yield "data: " + json.dumps({"error": str(e)}, ensure_ascii=False) + "\n\n"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    article = (data.get("article") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "deepseek-v4-flash").strip()
    if not article:
        return jsonify({"error": "文章不能为空"}), 400
    if not api_key:
        return jsonify({"error": "请先在设置里填写你自己的 API Key"}), 400
    client = make_client(api_key, base_url)
    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
        {"role": "user", "content": article},
    ]
    return Response(sse_stream(client, model, messages, 0.7, 16384),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "deepseek-v4-flash").strip()
    message = (data.get("message") or "").strip()
    context = (data.get("context") or "").strip()
    article = (data.get("article") or "").strip()
    history = data.get("history") or []
    if not api_key:
        return jsonify({"error": "请先在设置里填写你自己的 API Key"}), 400
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if article:
        messages.append({"role": "system",
                         "content": "以下是用户当前正在学习的文章/笔记，作为背景参考（仅在相关且有独特用法时引用）：\n\n" + article[:6000]})
    for h in history[-10:]:
        role, content = h.get("role"), h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    user_content = f"用户选中的文本：\n{context}\n\n问题：{message}" if context else message
    messages.append({"role": "user", "content": user_content})

    client = make_client(api_key, base_url)
    return Response(sse_stream(client, model, messages, 0.7, 2048),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/exercises", methods=["POST"])
def exercises():
    data = request.get_json(force=True)
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "deepseek-v4-flash").strip()
    article = (data.get("article") or "").strip()
    if not api_key:
        return jsonify({"error": "请先在设置里填写你自己的 API Key"}), 400
    if not article:
        return jsonify({"error": "没有文章内容，无法出题"}), 400

    client = make_client(api_key, base_url)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": EXERCISE_SYSTEM_PROMPT},
                      {"role": "user", "content": article[:8000]}],
            temperature=0.5, max_tokens=3000,
        )
        raw = resp.choices[0].message.content.strip()
        # 去掉可能的代码块围栏
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
        # 容错：截取第一个 { 到最后一个 }
        if not raw.startswith("{"):
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                raw = m.group(0)
        parsed = json.loads(raw)
        return jsonify(parsed)
    except json.JSONDecodeError:
        return jsonify({"error": "题目解析失败，请重试"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ping")
def ping():
    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
