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
# 笔记生成提示词（保留脚注；含选择标准 + 脚注纪律 + 长难句语法板块）
# ---------------------------------------------------------------------------
ANALYZE_SYSTEM_PROMPT = """分析下面的外语文章，做成一份个人学习笔记。文章可能是英语、日语、德语、韩语、西班牙语等任意语种——请先自动识别语种，再按该语种做词汇与语法分析；所有讲解、释义一律用中文，仿写/例句用原文的语言。

【最重要】只输出最终的笔记本身。绝对不要输出任何思考过程、自我检查、对脚注编号的推敲、草稿或说明性文字；不要把文章重复写第二遍；不要写“注：”“检查一下”之类的话。发现问题就直接在正文里改好，不要把纠结过程写出来。

### 关于原文清理（重要）
用户复制的原文往往很乱，因为外刊多为分栏排版。请在“文章展示”板块先把版面理顺：合并被分栏拆散、交错拼接的句子；修复行尾连字符断词（如 "infor-\\nmation" → "information"）；删除混入正文的页眉、页脚、页码、栏目名、图注等杂质；按语义重新分段。只做版面整理，尽量忠实原文用词，不要改写句子内容。

### 要求概览
- 文章展示 → 词汇词组精析 → 长难句语法精讲 → 句子赏析 → 写作手法 → 背诵速查表，六个板块缺一不可。
- 各板块内容尽量详尽，把值得学习的地方都挖掘出来。
- 行文简洁清晰，像自己写给自己的笔记，不要导师口吻。
- 若对某处史实或用法不确定，标注“(存疑，请以教材/原文为准)”。

## 一、文章展示
- 用二级标题“## 文章”开头，然后给出整理后的文章全文。

【词汇标记 —— 宽收】把值得学的地道词汇/词组用 **加粗** 标记，并紧跟一个脚注标记 [^n]（n 从 1 递增）。重复只标首次出现。
选择标准（按学习者中高级水平，满足其一就标）：地道搭配 / 词组 / 短语动词 / 习语（最优先）；相对进阶或精准的单词；熟词僻义；生动有画面感的动词、形容词；外刊学术高频的正式书面表达。只跳过极基础日常词和无学习价值的专有名词。**覆盖全文、不设上限，宁多勿漏**，保证词汇量充足。

【脚注规则 —— 简单照做即可，别想复杂】
- 脚注 [^n] **只加在加粗词汇/词组的后面**。斜体句子后面**绝对不要**加 [^n]，斜体句不参与脚注编号。
- 按加粗词出现的先后，从 1 开始依次编号（1、2、3……），每个加粗词一个编号。
- 每个编号在“词汇词组精析”里写一条对应定义即可。不用担心是否“对齐每个位置”，只要加粗词和它的定义一一对应就行。

【句子标记 —— 宁精勿滥】用 *斜体* 标记值得学习/仿写的精彩句子（斜体句后不加任何 [^n]），满足其一即可：
- 修辞：比喻、类比、拟人、对照、平行、反复、递进；
- 句法精巧：倒装、破折号收尾、插入语、圆周句 / 松散句、同位语堆叠；
- 警句格言式：凝练有力、可独立引用；
- 生动的动词或意象、有节奏感。
避免只传递信息、平铺直叙、无写作借鉴价值的句子。**覆盖面**：开头、中段、结尾都要照顾到，别只集中在一段；同类句式挑最好的一两句、去掉雷同；大致每 150–200 词挑 1–2 句最值得的。
- 斜体句子只在正文里就地标注，**不要**在文末或任何位置再单独罗列成清单。
- **一致性要求（重要）**：凡是你将在「句子赏析」或「写作手法·原文呈现」里用到的句子，都必须先在正文用 *斜体* 标注好，做到「原文标了＝后面会讲」「后面讲了＝原文一定有标」一一对应，绝不遗漏。「长难句语法精讲」里引用的句子**不需要**标斜体。

## 二、词汇词组精析
二级标题“## 📖 词汇词组精析”，按脚注顺序解析每一个，一个不能少。每条定义顶格另起一行、以 [^n]: 开头，编号与正文严格对应。格式：

[^n]: **词/词组** (词性)
核心释义 + 为什么地道。
📖 联动：(具体影视台词或外刊句子，必须完整)
💡 仿写：(完整的仿写句，用原文的语言)

- 脚注内部使用 <br> 换行。
- 脚注之间空一行。

## 三、长难句语法精讲
二级标题“## 🧩 长难句语法精讲”。挑出文中**较难读懂或有代表性的长难句**（长句、各类从句、非谓语、倒装、强调、虚拟、插入、省略等），重在帮读者读懂，与“句子赏析”挑的漂亮句尽量错开、不重复。每句用有序列表的一项，包含：
- **原句**：...
- **主干**：去掉修饰后的核心 S+V+O
- **结构拆解**：标出各成分（主句 / 从句、非谓语、插入语、省略、倒装、强调等），并点明用到的语法点名称
- **参考译文**：...

## 四、句子赏析
二级标题“## 🖋️ 精彩句子赏析”。逐一赏析前面用 *斜体* 标出的每一个句子。每个句子用有序列表的一项，包含三行：
- **原句**：...
- **妙处**：...（结构、修辞、用词、节奏等，简明点出）
- **仿写**：...（模仿其特点写一个完整英文句）

## 五、写作手法分析
二级标题“## ✍️ 写作手法仿写”。选出文中突出的写作技巧，每个技巧的名称用三级标题（### 技巧名称）开头，其下包含：
- **原文呈现**：引用文中句子
- **效用分析**：它为什么好
- **实战仿写**：用不同主题写一个段落（用原文的语言），真正用上该技巧

## 六、背诵速查表
二级标题“## 📋 背诵速查表”。用表格列出所有加粗词汇/词组，列：表达 | 释义 | 场景。

整份笔记用 Markdown 输出。"""

CHAT_SYSTEM_PROMPT = """你是一位专业的英语语言与写作导师，帮助用户深入理解英文文章。用户可以自由提任何问题，不限于选中的文本。

回答原则：
1. 先给出常规、通用的解释（词义、语法、用法、翻译等），准确简洁。
2. 如果用户选中了某段文本，或问题与正在学习的文章相关，再补充说明它在本文语境中的用法——但仅当这种用法确实有独特、值得一提之处时才补充；常规用法不必强行关联。
3. 不确定的史实或用法要如实说明，不要编造。

回答用中文，简洁、准确、有帮助。"""

EXERCISE_SYSTEM_PROMPT = """你是外语阅读理解出题老师。根据用户给的文章（先自动识别其语种），出 5 道阅读理解选择题，覆盖主旨大意、细节理解、词义猜测、推理判断、作者态度等题型。每题 4 个选项，只有一个正确答案。

严格只输出 JSON，不要任何多余文字、不要用代码块包裹，格式：
{"questions":[{"q":"题干","options":["A. ...","B. ...","C. ...","D. ..."],"answer":0,"explanation":"中文解析：为什么这个对、别的错"}]}

题干和选项用文章原文的语言，explanation 用中文。answer 是正确选项的下标（0-3）。"""

DEEPDIVE_SYSTEM_PROMPT = """IMPORTANT: Write your ENTIRE response in English only. Even if the material given to you is in Chinese, you must still write everything in English.

You are a sharp, well-read current-affairs analyst and critical thinker. The user is studying a foreign-language article and wants to think about it more deeply.

Write an original, thought-provoking analysis IN ENGLISH. Do NOT merely summarize. Instead:
- Draw out the core argument and the assumptions or biases behind it.
- Connect the topic to broader current affairs, history, economics, technology or geopolitics, with concrete real-world examples.
- Offer multiple perspectives, including counterarguments a thoughtful critic would raise.
- Surface second-order effects, tensions and open questions worth pondering.
- End with 2-3 sharp questions that broaden the reader's worldview.

Use clear Markdown with short section headings. Be substantive and specific, not generic. Aim for depth over length.

Reminder: the entire response MUST be in English."""

TRANSLATE_SYSTEM_PROMPT = """把用户给的文本翻译成自然、通顺的中文。只输出中文译文，不要原文、不要注释、不要任何多余的话。"""

DISCUSS_SYSTEM_PROMPT = """You are the user's English discussion partner and writing coach. The user is a learner practicing English by discussing the topic below with you. Always reply IN ENGLISH.

For each of the user's messages, do TWO things, in this order:
1. **Polish** — If the user's English is awkward, unclear or grammatically off, briefly show a smoother, more natural version. Start this with "✍️ Polished: ...". Keep it short; do not nitpick if the message is already fine (in that case skip this part or just say "Your English reads well.").
2. **Discuss** — Then engage genuinely with their idea: agree/push back with reasons, add a fresh angle or example, and end with one question that moves the thinking forward.

Be encouraging but intellectually honest. Keep it conversational and reasonably concise."""


def make_client(api_key, base_url):
    if not base_url:
        base_url = "https://api.deepseek.com"
    return OpenAI(api_key=api_key, base_url=base_url)


def lang_note(lang):
    """可选的语种兜底：默认 auto 时不加任何指令（省 token）。"""
    lang = (lang or "auto").strip()
    if not lang or lang.lower() == "auto":
        return None
    return "这篇文章的语言是：%s。请按该语言分析（若与实际不符，以实际原文语种为准）。" % lang


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
    messages = [{"role": "system", "content": ANALYZE_SYSTEM_PROMPT}]
    note = lang_note(data.get("lang"))
    if note:
        messages.append({"role": "system", "content": note})
    messages.append({"role": "user", "content": article})
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
        # 只带精简背景，省 token（无状态每次都要重发）
        messages.append({"role": "system",
                         "content": "以下是用户当前正在学习的文章/笔记片段，作为背景参考（仅在相关且有独特用法时引用）：\n\n" + article[:2500]})
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
    ex_msgs = [{"role": "system", "content": EXERCISE_SYSTEM_PROMPT}]
    note = lang_note(data.get("lang"))
    if note:
        ex_msgs.append({"role": "system", "content": note})
    ex_msgs.append({"role": "user", "content": article[:8000]})
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=ex_msgs,
            temperature=0.5, max_tokens=3000,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
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


@app.route("/deepdive", methods=["POST"])
def deepdive():
    data = request.get_json(force=True)
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "deepseek-v4-flash").strip()
    article = (data.get("article") or "").strip()
    if not api_key:
        return jsonify({"error": "请先在设置里填写你自己的 API Key"}), 400
    if not article:
        return jsonify({"error": "没有文章内容，无法分析"}), 400
    client = make_client(api_key, base_url)
    messages = [
        {"role": "system", "content": DEEPDIVE_SYSTEM_PROMPT},
        {"role": "user", "content": article[:9000]},
    ]
    return Response(sse_stream(client, model, messages, 0.8, 4096),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/discuss", methods=["POST"])
def discuss():
    data = request.get_json(force=True)
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "deepseek-v4-flash").strip()
    message = (data.get("message") or "").strip()
    analysis = (data.get("analysis") or "").strip()   # 深度思考正文
    article = (data.get("article") or "").strip()
    history = data.get("history") or []
    if not api_key:
        return jsonify({"error": "请先在设置里填写你自己的 API Key"}), 400
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    messages = [{"role": "system", "content": DISCUSS_SYSTEM_PROMPT}]
    ctx = ""
    if analysis:
        ctx += "The analysis under discussion:\n" + analysis[:3500] + "\n\n"
    if article:
        ctx += "Source article excerpt:\n" + article[:2000]
    if ctx:
        messages.append({"role": "system", "content": ctx})
    for h in history[-8:]:
        role, content = h.get("role"), h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    client = make_client(api_key, base_url)
    return Response(sse_stream(client, model, messages, 0.7, 1500),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json(force=True)
    api_key = (data.get("api_key") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    model = (data.get("model") or "deepseek-v4-flash").strip()
    text = (data.get("text") or "").strip()
    if not api_key:
        return jsonify({"error": "请先在设置里填写你自己的 API Key"}), 400
    if not text:
        return jsonify({"error": "没有可翻译的内容"}), 400
    client = make_client(api_key, base_url)
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
        {"role": "user", "content": text[:6000]},
    ]
    return Response(sse_stream(client, model, messages, 0.3, 2048),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/ping")
def ping():
    return "ok"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
