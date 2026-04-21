import asyncio
import json
import re
import textwrap
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


CONFIG_JSON = {
  "CONFIGCODE": {
    "navegador": "chromium",
    "driver": "playwright",
    "headless": false,
    "timeout": 30,
    "delay": 500,
    "poll_interval": 10,
    "max_workers": 3,
    "profile": "",
    "chromedriver": "",
    "runtime_mode": "loop",
    "heatbear": 15
  },
  "CONFIG": {
    "nome": "WhatsApp BOT",
    "versao": "0.0.2",
    "empresa": "XXXXXXX",
    "funcao_script": "Automação com Selenium",
    "dependencias": [
      "selenium",
      "time"
    ],
    "executar": "comecar"
  }
}

FLOW_DEFINITION = {
  "name": "WhatsApp BOT Local",
  "nodes": [
    {
      "id": "start_text-d76edcc0-dc2b-4ff9-b4a4-3773bf228649",
      "type": "start_text",
      "position": {
        "x": 120,
        "y": 80
      },
      "data": {
        "nodeType": "start_text",
        "title": "Boas-vindas",
        "description": "Inicia a sessão já respondendo a mensagem recebida.",
        "runtimeFamily": "trigger",
        "accent": "#8ef3d5",
        "category": "Gatilhos",
        "settings": {
          "text": "Olá! Sou o bot local do WhatsApp. Digite 1 para comercial ou qualquer outra mensagem para suporte."
        },
        "customCode": ""
      }
    },
    {
      "id": "input_choice-ddcc4878-3068-4fe7-90b2-41327c6f19aa",
      "type": "input_choice",
      "position": {
        "x": 460,
        "y": 80
      },
      "data": {
        "nodeType": "input_choice",
        "title": "Ler intenção",
        "description": "Normaliza resposta em uma variável de opção.",
        "runtimeFamily": "input",
        "accent": "#6ac3ff",
        "category": "Entrada",
        "settings": {
          "variable_name": "opcao"
        },
        "customCode": ""
      }
    },
    {
      "id": "condition-75fd13c5-05f3-407c-96e8-e145eb75da9d",
      "type": "condition",
      "position": {
        "x": 800,
        "y": 80
      },
      "data": {
        "nodeType": "condition",
        "title": "Rota Comercial?",
        "description": "Executa um desvio verdadeiro ou falso.",
        "runtimeFamily": "condition",
        "accent": "#ff7aa8",
        "category": "Lógica",
        "settings": {
          "expression": "str(variables.get('opcao', '')).strip().lower() in {'1', 'comercial', 'vendas'}"
        },
        "customCode": ""
      }
    },
    {
      "id": "whatsapp_message-2319fb79-840f-4748-bea5-eb4c2ff5bfc5",
      "type": "whatsapp_message",
      "position": {
        "x": 1140,
        "y": -80
      },
      "data": {
        "nodeType": "whatsapp_message",
        "title": "Resposta comercial",
        "description": "Envia uma mensagem de texto no WhatsApp.",
        "runtimeFamily": "message",
        "accent": "#43f0a7",
        "category": "WhatsApp",
        "settings": {
          "text": "Perfeito. Vou seguir com o fluxo comercial para {{contact}}."
        },
        "customCode": ""
      }
    },
    {
      "id": "human_handoff-15037d74-1929-4ddc-833a-6a65da876dfa",
      "type": "human_handoff",
      "position": {
        "x": 1140,
        "y": 240
      },
      "data": {
        "nodeType": "human_handoff",
        "title": "Suporte humano",
        "description": "Sinaliza que o contato vai para atendimento humano.",
        "runtimeFamily": "session",
        "accent": "#ff9bd8",
        "category": "WhatsApp",
        "settings": {
          "queue": "suporte_humano"
        },
        "customCode": ""
      }
    },
    {
      "id": "session_end-4c2f2194-7d99-4785-925d-bed1795ada95",
      "type": "session_end",
      "position": {
        "x": 1480,
        "y": 80
      },
      "data": {
        "nodeType": "session_end",
        "title": "Encerrar sessão",
        "description": "Encerra a sessão do contato atual.",
        "runtimeFamily": "session",
        "accent": "#ff857a",
        "category": "WhatsApp",
        "settings": {
          "reason": "fluxo_concluido"
        },
        "customCode": ""
      }
    }
  ],
  "edges": [
    {
      "id": "edge-af24dd84-da69-48a7-8f94-e39c90978c6a",
      "source": "start_text-d76edcc0-dc2b-4ff9-b4a4-3773bf228649",
      "target": "input_choice-ddcc4878-3068-4fe7-90b2-41327c6f19aa",
      "sourceHandle": null,
      "targetHandle": null,
      "type": "smoothstep",
      "data": {}
    },
    {
      "id": "edge-5c1571f3-5d10-4557-b59b-13fc5c2ed1da",
      "source": "input_choice-ddcc4878-3068-4fe7-90b2-41327c6f19aa",
      "target": "condition-75fd13c5-05f3-407c-96e8-e145eb75da9d",
      "sourceHandle": null,
      "targetHandle": null,
      "type": "smoothstep",
      "data": {}
    },
    {
      "id": "edge-f4f4d1a3-2219-4a40-8db8-7f7c0925aee2",
      "source": "condition-75fd13c5-05f3-407c-96e8-e145eb75da9d",
      "target": "whatsapp_message-2319fb79-840f-4748-bea5-eb4c2ff5bfc5",
      "sourceHandle": "condition-true",
      "targetHandle": null,
      "type": "smoothstep",
      "data": {
        "label": "Sim"
      }
    },
    {
      "id": "edge-8ea93696-9bbd-41fe-a802-1505dd7f1450",
      "source": "condition-75fd13c5-05f3-407c-96e8-e145eb75da9d",
      "target": "human_handoff-15037d74-1929-4ddc-833a-6a65da876dfa",
      "sourceHandle": "condition-false",
      "targetHandle": null,
      "type": "smoothstep",
      "data": {
        "label": "Não"
      }
    },
    {
      "id": "edge-7f10291b-8033-4e33-bf99-04bcf345856e",
      "source": "whatsapp_message-2319fb79-840f-4748-bea5-eb4c2ff5bfc5",
      "target": "session_end-4c2f2194-7d99-4785-925d-bed1795ada95",
      "sourceHandle": null,
      "targetHandle": null,
      "type": "smoothstep",
      "data": {}
    },
    {
      "id": "edge-34f843a5-c892-4ffe-b1e4-05b4f078aca2",
      "source": "human_handoff-15037d74-1929-4ddc-833a-6a65da876dfa",
      "target": "session_end-4c2f2194-7d99-4785-925d-bed1795ada95",
      "sourceHandle": null,
      "targetHandle": null,
      "type": "smoothstep",
      "data": {}
    }
  ]
}

CONFIGCODE = CONFIG_JSON["CONFIGCODE"]
CONFIG = CONFIG_JSON["CONFIG"]

TOP_CHAT_LIMIT = 10
SESSION_IDLE_LIMIT = 10


def log(message):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}")


def sanitize_name(value):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value or "").strip("_") or "unknown"


def interpolate(template, ctx):
    if template is None:
        return ""
    template = str(template)
    variables = ctx.get("variables", {})

    def replace(match):
        key = match.group(1).strip()
        if key == "message":
            return str(ctx.get("message", ""))
        if key == "contact":
            return str(ctx.get("contact", ""))
        if key == "node_title":
            return str(ctx.get("node", {}).get("data", {}).get("title", ""))
        if key in variables:
            return str(variables.get(key, ""))
        return str(ctx.get(key, ""))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template)


def build_indexes(flow):
    nodes = {node["id"]: node for node in flow.get("nodes", [])}
    outgoing = {}
    incoming = {node_id: 0 for node_id in nodes}
    for edge in flow.get("edges", []):
        outgoing.setdefault(edge["source"], []).append(edge)
        incoming[edge["target"]] = incoming.get(edge["target"], 0) + 1
    return nodes, outgoing, incoming


def edge_priority(edge):
    handle = edge.get("sourceHandle") or ""
    if "true" in handle:
        return 0
    if "false" in handle:
        return 1
    return 2


def default_next_edge(outgoing_map, node_id):
    edges = sorted(outgoing_map.get(node_id, []), key=edge_priority)
    return edges[0] if edges else None


def branch_edge(outgoing_map, node_id, truthy):
    edges = sorted(outgoing_map.get(node_id, []), key=edge_priority)
    if not edges:
        return None
    for edge in edges:
        handle = (edge.get("sourceHandle") or "").lower()
        if truthy and "true" in handle:
            return edge
        if (not truthy) and "false" in handle:
            return edge
    if len(edges) > 1:
        return edges[0] if truthy else edges[1]
    return edges[0]


def choose_start_node(nodes, incoming):
    preferred = []
    for node in nodes.values():
        if node["type"] in {"start", "start_text", "session_start"}:
            preferred.append(node)
    if preferred:
        preferred.sort(key=lambda item: (incoming.get(item["id"], 0), item["id"]))
        return preferred[0]["id"]
    if nodes:
        return sorted(nodes.keys())[0]
    return None


async def browser_context(playwright):
    browser_name = str(CONFIGCODE.get("navegador", "chromium")).lower()
    headless = bool(CONFIGCODE.get("headless", False))
    timeout_ms = int(CONFIGCODE.get("timeout", 30)) * 1000
    profile = CONFIGCODE.get("profile") or ""

    browser_type = getattr(playwright, browser_name, playwright.chromium)
    launch_kwargs = {"headless": headless, "slow_mo": int(CONFIGCODE.get("delay", 500))}

    if profile:
        context = await browser_type.launch_persistent_context(profile, **launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()
    else:
        browser = await browser_type.launch(**launch_kwargs)
        context = await browser.new_context()
        page = await context.new_page()

    page.set_default_timeout(timeout_ms)
    await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
    return context, page


async def wait_for_whatsapp_ready(page):
    timeout_ms = int(CONFIGCODE.get("timeout", 30)) * 1000
    selectors = [
        "#pane-side",
        "div[aria-label='Chat list']",
        "div[role='grid']",
    ]
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            log("WhatsApp Web pronto.")
            return
        except PlaywrightTimeoutError:
            continue
    log("WhatsApp Web ainda não exibiu a lista. Faça login pelo QR Code se necessário.")
    await page.wait_for_timeout(5000)


async def first_text(locator, selectors):
    for selector in selectors:
        candidate = locator.locator(selector).first
        if await candidate.count():
            text = (await candidate.inner_text()).strip()
            if text:
                return text
    return ""


async def read_top_chats(page, limit=TOP_CHAT_LIMIT):
    container = page.locator("#pane-side [role='listitem']")
    count = await container.count()
    chats = []
    for index in range(min(limit, count)):
        row = container.nth(index)
        title = await first_text(
            row,
            [
                "span[title]",
                "span[dir='auto']",
                "div[role='gridcell'] span",
            ],
        )
        unread_text = await first_text(
            row,
            [
                "span[aria-label*='unread']",
                "span[data-testid='icon-unread-count']",
                "div[aria-label*='unread']",
            ],
        )
        digits = re.findall(r"\d+", unread_text)
        unread = int(digits[0]) if digits else (1 if unread_text else 0)
        chats.append(
            {
                "index": index,
                "title": title or f"chat_{index}",
                "unread": unread,
            }
        )
    return chats


async def open_chat_by_index(page, index):
    row = page.locator("#pane-side [role='listitem']").nth(index)
    if await row.count():
        await row.click()
        await page.wait_for_timeout(250)


async def search_and_open_chat(page, contact):
    search_box = page.locator("div[contenteditable='true'][data-tab='3']").first
    if not await search_box.count():
        search_box = page.locator("div[role='textbox']").first
    if not await search_box.count():
        return False
    await search_box.click()
    await search_box.fill("")
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await search_box.type(contact, delay=30)
    await page.wait_for_timeout(400)
    result = page.locator("#pane-side [role='listitem']").first
    if not await result.count():
        return False
    await result.click()
    await page.wait_for_timeout(250)
    return True


async def active_contact(page):
    selectors = [
        "header span[title]",
        "header h1",
        "div[data-testid='conversation-info-header-chat-title'] span",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if await locator.count():
            text = (await locator.inner_text()).strip()
            if text:
                return text
    return "contato-desconhecido"


async def last_inbound_message(page):
    candidates = page.locator("div.message-in")
    count = await candidates.count()
    if count == 0:
        return {"id": "", "text": "", "direction": "in"}
    bubble = candidates.nth(count - 1)
    text = await first_text(
        bubble,
        [
            "span.selectable-text span",
            "div.copyable-text span",
            "span[dir='ltr']",
        ],
    )
    bubble_html = await bubble.inner_html()
    match = re.search(r"data-id=\"([^\"]+)\"", bubble_html)
    message_id = match.group(1) if match else f"msg-{count}"
    return {"id": message_id, "text": text.strip(), "direction": "in"}


async def send_text(page, text):
    if not text:
        return
    box = page.locator("footer div[contenteditable='true']").last
    if not await box.count():
        box = page.locator("div[contenteditable='true'][role='textbox']").last
    if not await box.count():
        raise RuntimeError("Campo de mensagem do WhatsApp não encontrado.")
    await box.click()
    await box.type(text, delay=20)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(250)
    log(f"Mensagem enviada: {text[:80]}")


def perform_http_request(method, url, payload):
    if not url:
        return {"ok": False, "error": "URL vazia"}
    method = method.upper()
    data = None
    headers = {"Content-Type": "application/json"}
    if payload:
        data = payload.encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=int(CONFIGCODE.get("timeout", 30))) as response:
            text = response.read().decode("utf-8", errors="ignore")
            return {
                "ok": True,
                "status": response.status,
                "body": text,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "body": exc.read().decode("utf-8", errors="ignore"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def run_custom_code(code, ctx, session, state, page, helpers):
    if not code or not code.strip():
        return None
    namespace = {}
    function_source = "async def __user_code__(ctx, session, state, page, helpers):\n" + textwrap.indent(code, "    ")
    exec(function_source, globals(), namespace)
    return await namespace["__user_code__"](ctx, session, state, page, helpers)


def safe_eval(expression, ctx, default=None):
    expression = (expression or "").strip()
    if not expression:
        return default
    scope = {
        "message": ctx.get("message", ""),
        "contact": ctx.get("contact", ""),
        "variables": ctx.get("variables", {}),
        "session": ctx.get("session"),
        "state": ctx.get("state"),
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "re": re,
    }
    try:
        return eval(expression, {"__builtins__": {}}, scope)
    except Exception:
        return default


def parse_json_template(template, ctx):
    rendered = interpolate(template, ctx)
    if not rendered:
        return {}
    try:
        return json.loads(rendered)
    except json.JSONDecodeError:
        return {"raw": rendered}


async def execute_node(node, nodes, outgoing_map, ctx, session, state, page):
    data = node.get("data", {})
    settings = data.get("settings", {})
    family = data.get("runtimeFamily") or "generic"
    ctx["node"] = node
    ctx["variables"] = session.setdefault("variables", {})
    ctx["session"] = session
    ctx["state"] = state

    helpers = {
        "send_text": send_text,
        "safe_eval": safe_eval,
        "interpolate": interpolate,
        "perform_http_request": perform_http_request,
        "parse_json_template": parse_json_template,
    }

    if node["type"] == "start_text":
        await send_text(page, interpolate(settings.get("text", ""), ctx))
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "trigger":
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "message":
        await send_text(page, interpolate(settings.get("text", ""), ctx))
        edge = default_next_edge(outgoing_map, node["id"])
        if data.get("customCode"):
            await run_custom_code(data.get("customCode", ""), ctx, session, state, page, helpers)
        return edge["target"] if edge else None, False

    if family == "input":
        variable_name = settings.get("variable_name", "user_input")
        if not ctx.get("message"):
            return node["id"], True
        value = ctx.get("message", "")
        if node["type"] == "input_number":
            digits = re.findall(r"-?\d+(?:\.\d+)?", value)
            value = float(digits[0]) if digits else 0
        session["variables"][variable_name] = value
        ctx["variables"][variable_name] = value
        ctx["message"] = ""
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "condition":
        result = safe_eval(settings.get("expression", ""), ctx, False)
        edge = branch_edge(outgoing_map, node["id"], bool(result))
        if data.get("customCode"):
            custom_result = await run_custom_code(data.get("customCode", ""), ctx, session, state, page, helpers)
            if custom_result is not None:
                result = custom_result
                edge = branch_edge(outgoing_map, node["id"], bool(result))
        return edge["target"] if edge else None, False

    if family == "wait":
        tracker = session.setdefault("wait_tracker", {})
        current_cycle = state["heartbeat_cycle"]
        node_key = node["id"]
        requested = max(1, int(settings.get("heartbeat_cycles", 1)))
        if node_key not in tracker:
            tracker[node_key] = current_cycle + requested
            return node["id"], True
        if current_cycle < tracker[node_key]:
            return node["id"], True
        tracker.pop(node_key, None)
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "integration":
        payload = json.dumps(parse_json_template(settings.get("payload", "{}"), ctx), ensure_ascii=False)
        method = settings.get("method", "POST")
        url = settings.get("url", "")
        response = await asyncio.to_thread(perform_http_request, method, url, payload)
        session["variables"]["integration_last_result"] = response
        session["variables"]["integration_name"] = settings.get("integration_name", "")
        edge = default_next_edge(outgoing_map, node["id"])
        if data.get("customCode"):
            await run_custom_code(data.get("customCode", ""), ctx, session, state, page, helpers)
        return edge["target"] if edge else None, False

    if family == "data":
        if node["type"] == "set_variable":
            name = settings.get("name", "temp")
            session["variables"][name] = safe_eval(settings.get("value", "None"), ctx, settings.get("value"))
        elif node["type"] == "read_variable":
            origin = settings.get("name", "")
            target = settings.get("target", origin or "value")
            session["variables"][target] = session["variables"].get(origin)
        elif node["type"] == "json_parser":
            source_name = settings.get("source", "message")
            source_value = ctx.get(source_name) or session["variables"].get(source_name, "")
            try:
                parsed = json.loads(source_value)
            except Exception:
                parsed = {"raw": source_value}
            session["variables"][settings.get("target", "payload")] = parsed
        elif node["type"] == "openai_prompt":
            session["variables"]["prompt_template"] = settings.get("value", "")
        edge = default_next_edge(outgoing_map, node["id"])
        if data.get("customCode"):
            await run_custom_code(data.get("customCode", ""), ctx, session, state, page, helpers)
        return edge["target"] if edge else None, False

    if family == "output":
        if node["type"] == "output_log":
            log(interpolate(settings.get("message", ""), ctx))
        elif node["type"] == "output_json":
            state["last_output_json"] = parse_json_template(settings.get("payload", "{}"), ctx)
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "session":
        if node["type"] == "session_start":
            session["status"] = "active"
            session["tags"] = list(set(session.get("tags", []) + [settings.get("tag", "nova_sessao")]))
        elif node["type"] == "session_end":
            session["status"] = "closed"
            session["close_reason"] = settings.get("reason", "done")
            return None, False
        elif node["type"] == "human_handoff":
            session["status"] = "handoff"
            session["queue"] = settings.get("queue", "atendimento_humano")
        elif node["type"] == "tag_contact":
            session["tags"] = list(set(session.get("tags", []) + [settings.get("tag", "tag")]))
        elif node["type"] == "assign_queue":
            session["queue"] = settings.get("queue", "padrao")
        edge = default_next_edge(outgoing_map, node["id"])
        if data.get("customCode"):
            await run_custom_code(data.get("customCode", ""), ctx, session, state, page, helpers)
        return edge["target"] if edge else None, False

    if family == "system":
        if node["type"] == "heartbeat_guard":
            min_cycle = int(settings.get("min_cycle", 0))
            if state["heartbeat_cycle"] < min_cycle:
                return node["id"], True
        elif node["type"] == "recent_chats":
            state["recent_chats"] = await read_top_chats(page, int(settings.get("limit", TOP_CHAT_LIMIT)))
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "router":
        if node["type"] == "go_to":
            target_node_id = settings.get("target_node_id", "")
            if target_node_id and target_node_id in nodes:
                return target_node_id, False
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    if family == "code" or data.get("customCode"):
        result = await run_custom_code(data.get("customCode", ""), ctx, session, state, page, helpers)
        if isinstance(result, str) and result in nodes:
            return result, False
        edge = default_next_edge(outgoing_map, node["id"])
        return edge["target"] if edge else None, False

    edge = default_next_edge(outgoing_map, node["id"])
    return edge["target"] if edge else None, False


async def advance_flow(flow_indexes, session, state, page, trigger_message):
    nodes, outgoing_map, incoming = flow_indexes
    current = session.get("current_node") or choose_start_node(nodes, incoming)
    ctx = {
        "contact": session["contact"],
        "message": trigger_message or "",
        "variables": session.setdefault("variables", {}),
        "state": state,
    }
    steps = 0
    while current and steps < 80:
        node = nodes[current]
        next_node, pause = await execute_node(node, nodes, outgoing_map, ctx, session, state, page)
        if pause:
            session["current_node"] = next_node or current
            return
        current = next_node
        steps += 1
    session["current_node"] = current


async def ensure_session(state, contact):
    sessions = state.setdefault("sessions", {})
    if contact not in sessions:
        sessions[contact] = {
            "contact": contact,
            "status": "active",
            "current_node": None,
            "variables": {},
            "history": [],
            "idle_heartbeats": 0,
            "last_message_id": "",
            "started_at": datetime.now().isoformat(),
        }
        log(f"Nova sessão criada para {contact}")
    return sessions[contact]


async def inspect_new_messages(page, state, flow_indexes):
    chats = await read_top_chats(page, TOP_CHAT_LIMIT)
    state["recent_chats"] = chats
    for chat in chats:
        if chat["unread"] <= 0:
            continue
        await open_chat_by_index(page, chat["index"])
        contact = await active_contact(page)
        session = await ensure_session(state, contact)
        inbound = await last_inbound_message(page)
        if not inbound["id"] or inbound["id"] == session.get("last_message_id"):
            continue
        session["idle_heartbeats"] = 0
        session["last_message_id"] = inbound["id"]
        session["history"].append({"role": "user", "text": inbound["text"], "id": inbound["id"]})
        await advance_flow(flow_indexes, session, state, page, inbound["text"])


async def follow_active_sessions(page, state, flow_indexes):
    sessions = list(state.get("sessions", {}).values())
    for session in sessions:
        if session.get("status") in {"closed", "expired"}:
            continue
        opened = await search_and_open_chat(page, session["contact"])
        if not opened:
            session["idle_heartbeats"] = session.get("idle_heartbeats", 0) + 1
            continue
        inbound = await last_inbound_message(page)
        if inbound["id"] and inbound["id"] != session.get("last_message_id"):
            session["last_message_id"] = inbound["id"]
            session["idle_heartbeats"] = 0
            session["history"].append({"role": "user", "text": inbound["text"], "id": inbound["id"]})
            await advance_flow(flow_indexes, session, state, page, inbound["text"])
        else:
            session["idle_heartbeats"] = session.get("idle_heartbeats", 0) + 1

        if session["idle_heartbeats"] >= SESSION_IDLE_LIMIT:
            session["status"] = "expired"
            session["close_reason"] = "heartbeat-timeout"
            log(f"Sessão encerrada por inatividade: {session['contact']}")


async def main_loop():
    state = {
        "heartbeat_cycle": 0,
        "sessions": {},
        "recent_chats": [],
        "last_output_json": {},
    }
    flow_indexes = build_indexes(FLOW_DEFINITION)
    poll_seconds = max(1, int(CONFIGCODE.get("heatbear", 15)))

    async with async_playwright() as playwright:
        context, page = await browser_context(playwright)
        try:
            await wait_for_whatsapp_ready(page)
            while True:
                state["heartbeat_cycle"] += 1
                log(f"Heartbeat #{state['heartbeat_cycle']}")
                await inspect_new_messages(page, state, flow_indexes)
                await follow_active_sessions(page, state, flow_indexes)
                await asyncio.sleep(poll_seconds)
        finally:
            await context.close()


def run():
    asyncio.run(main_loop())


if __name__ == "__main__":
    run()
