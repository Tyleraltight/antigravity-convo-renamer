# -*- coding: utf-8 -*-
"""
Antigravity Conversation Renamer.
- Formats sidebar conversation titles as compact 'MMDD|<concise theme>' labels
  within <= 10 Chinese chars (20 display units) or <= 15 ASCII chars.
- Supports optional per-workspace rules and custom phrase mappings via rules.json.
- Discovers live language_server endpoints via daemon/hub_*.json (Antigravity 2.34+)
  with legacy CLI --csrf_token fallback, strict PID/loopback ownership checks, and
  proxy-free localhost RPC updates.
"""

import argparse
import ctypes
from ctypes import wintypes
import glob
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import ssl
import sys
import urllib.request
from datetime import datetime
import zoneinfo

import psutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "rules.json")

LOG_DIR = os.path.expanduser(r"~\.gemini\antigravity\logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "auto_rename.log")

_log_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=1_048_576, backupCount=3, encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_log_handler])
logger = logging.getLogger("AntigravityRenamer")

PB_PATH = os.path.expanduser(r"~\.gemini\antigravity\agyhub_summaries_proto.pb")
BRAIN_DIR = os.path.expanduser(r"~\.gemini\antigravity\brain")
DAEMON_DIR = os.path.expanduser(r"~\.gemini\antigravity\daemon")

UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
PLACEHOLDER_TITLES = {"new conversation", "new chat", "untitled"}
MUTEX_NAME = "Local\\AntigravityAutoConvoRename"
ERROR_ALREADY_EXISTS = 183

DEFAULT_MAX_CJK_UNITS = 20
DEFAULT_MAX_ENG_CHARS = 15

DEFAULT_TECH_ALLOWLIST = {
    "API", "UI", "UX", "APK", "MCP", "FASTMCP", "JSON", "RPC", "HTTP", "HTTPS",
    "SQL", "CI", "CD", "CLI", "SSH", "AI", "LLM", "AGENT", "SWARM", "WEB",
    "APP", "CSS", "HTML", "JS", "TS", "VUE", "REACT", "PYTHON", "NODE",
    "DOCKER", "LINUX", "WINDOWS", "MACOS", "GITHUB", "GITLAB", "FIGMA",
    "NOTION", "ZOOM", "STRIPE", "GEMINI", "OPENAI", "CLAUDE", "GOOGLE",
    "CLOUD", "PRO", "DEVOPS", "BOT", "README", "PR", "ISSUE", "ANTIGRAVITY",
}

PRE_NORMALIZE_RULES = [
    ("UI界面Design", " UI Design "),
    ("UI界面Layout", " UI Layout "),
    ("UI界面", " UI "),
    ("缺陷问题", " Issues "),
    ("工作流Protocol", " Workflow Protocol "),
    ("架构And", " Architecture And "),
    ("技能Development", " Skill Development "),
    ("功能Updates", " Feature Updates "),
]

DEFAULT_SEMANTIC_TERMS = [
    ("project architecture review and enhancement", "项目架构审查完善"),
    ("architecture review and enhancement", "架构审查完善"),
    ("browser language auto-detection", "浏览器语言切换"),
    ("browser language auto detection", "浏览器语言切换"),
    ("detect user browser language", "浏览器语言切换"),
    ("reverse engineering", "逆向工程"),
    ("workflow setup guide", "工作流配置"),
    ("workflow setup", "工作流配置"),
    ("workflow optimization", "工作流优化"),
    ("workflow integration", "工作流集成"),
    ("api feature testing", "API功能测试"),
    ("feature testing", "功能测试"),
    ("feature implementation", "功能开发"),
    ("feature updates", "功能更新"),
    ("installation guide", "安装指南"),
    ("usage guide", "用法指南"),
    ("deployment guide", "部署指南"),
    ("profile optimization", "主页优化"),
    ("security audit", "安全审计"),
    ("security analysis", "安全分析"),
    ("code review", "代码审查"),
    ("architecture review", "架构审查"),
    ("progress check", "进度"),
    ("responsive layouts", "响应式布局"),
    ("responsive layout", "响应式布局"),
    ("responsive design", "移动端适配"),
    ("file cleanup", "文件清理"),
    ("memory management", "智能体记忆"),
    ("open source", "开源"),
    ("landing page", "落地页"),
    ("custom rules", "自定义规则"),
    ("installation", "安装"),
    ("installing", "安装"),
    ("install", "安装"),
    ("configuring", "配置"),
    ("configuration", "配置"),
    ("configure", "配置"),
    ("setting up", "配置"),
    ("setup", "配置"),
    ("deployment", "部署"),
    ("deploying", "部署"),
    ("deploy", "部署"),
    ("troubleshooting", "排查"),
    ("debugging", "排查"),
    ("debug", "排查"),
    ("refactoring", "重构"),
    ("refactor", "重构"),
    ("optimizing", "优化"),
    ("optimization", "优化"),
    ("optimize", "优化"),
    ("implementing", "实现"),
    ("implementation", "实现"),
    ("implement", "实现"),
    ("developing", "开发"),
    ("development", "开发"),
    ("develop", "开发"),
    ("building", "构建"),
    ("build", "构建"),
    ("testing", "测试"),
    ("test", "测试"),
    ("updating", "更新"),
    ("updates", "更新"),
    ("update", "更新"),
    ("verifying", "验证"),
    ("verify", "验证"),
    ("analyzing", "分析"),
    ("analysis", "分析"),
    ("reviewing", "审查"),
    ("review", "审查"),
    ("enhancement", "完善"),
    ("integration", "接入"),
    ("completion", "补全"),
    ("monitoring", "监控"),
    ("managing", "管理"),
    ("management", "管理"),
    ("migrating", "迁移"),
    ("migration", "迁移"),
    ("checking", "检查"),
    ("check", "检查"),
    ("fixing", "修复"),
    ("fix", "修复"),
    ("deleting", "删除"),
    ("delete", "删除"),
    ("editing", "编辑"),
    ("edit", "编辑"),
    ("cleaning", "清理"),
    ("cleanup", "清理"),
    ("packaging", "打包"),
    ("package", "打包"),
    ("workflow", "工作流"),
    ("protocol", "协议"),
    ("repository", "仓库"),
    ("repo", "仓库"),
    ("website", "网站"),
    ("environment", "环境"),
    ("architecture", "架构"),
    ("request", "请求"),
    ("guide", "指南"),
    ("script", "脚本"),
    ("skill", "技能"),
    ("skills", "技能"),
    ("feature", "功能"),
    ("features", "功能"),
    ("strategy", "策略"),
    ("plan", "方案"),
    ("documentation", "文档"),
    ("summary", "总结"),
    ("client", "客户端"),
    ("server", "服务端"),
    ("module", "模块"),
    ("logic", "逻辑"),
    ("project", "项目"),
    ("projects", "项目"),
    ("tool", "工具"),
    ("tools", "工具"),
    ("error", "报错"),
    ("errors", "报错"),
    ("issue", "问题"),
    ("issues", "问题"),
    ("design", "设计"),
    ("localhost", "本地"),
    ("agent", "Agent"),
    ("version", "版本"),
    ("new", "新"),
    ("ui", "UI"),
    ("api", "API"),
]

CANONICAL_ACRONYMS = [
    "API", "UI", "UX", "APK", "MCP", "CI/CD", "CI|CD", "DevOps", "Zoom",
    "Notion", "GitHub", "Stripe", "Pro", "Gemini", "OpenAI", "Claude",
    "Antigravity", "SQL", "Google", "Node.js",
]

COMPILED_ACRONYM_PATTERNS = [
    (re.compile(r"\b" + re.escape(acr) + r"\b", re.IGNORECASE), acr)
    for acr in CANONICAL_ACRONYMS
]

ENGLISH_STOPWORDS = {"the", "a", "an", "for", "of", "and", "to", "in", "on", "with", "this", "by", "from"}
ENGLISH_ABBREVS = [
    (re.compile(r"\bInstallation\b", re.IGNORECASE), "Install"),
    (re.compile(r"\bConfiguration\b", re.IGNORECASE), "Config"),
    (re.compile(r"\bManagement\b", re.IGNORECASE), "Mgmt"),
    (re.compile(r"\bArchitecture\b", re.IGNORECASE), "Arch"),
    (re.compile(r"\bEnvironment\b", re.IGNORECASE), "Env"),
    (re.compile(r"\bDevelopment\b", re.IGNORECASE), "Dev"),
    (re.compile(r"\bDocumentation\b", re.IGNORECASE), "Docs"),
    (re.compile(r"\bOptimization\b", re.IGNORECASE), "Opt"),
    (re.compile(r"\bIntegration\b", re.IGNORECASE), "Integ"),
    (re.compile(r"\bImplementation\b", re.IGNORECASE), "Impl"),
    (re.compile(r"\bRecommendations?\b", re.IGNORECASE), "Rec"),
    (re.compile(r"\bInformation\b", re.IGNORECASE), "Info"),
]


def load_rules_config(config_path=None):
    """Load optional external rules.json configuration, returning normalized settings."""
    path = config_path or DEFAULT_CONFIG_PATH
    cfg = {
        "tz": datetime.now().astimezone().tzinfo,
        "max_cjk_units": DEFAULT_MAX_CJK_UNITS,
        "max_eng_chars": DEFAULT_MAX_ENG_CHARS,
        "tech_allowlist": set(DEFAULT_TECH_ALLOWLIST),
        "semantic_patterns": [],
        "workspace_rules": [],
    }
    raw_terms = list(DEFAULT_SEMANTIC_TERMS)

    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("timezone"), str) and data["timezone"]:
                cfg["tz"] = zoneinfo.ZoneInfo(data["timezone"])
            if isinstance(data.get("max_cjk_units"), int) and data["max_cjk_units"] >= 8:
                cfg["max_cjk_units"] = data["max_cjk_units"]
            if isinstance(data.get("max_eng_chars"), int) and data["max_eng_chars"] >= 8:
                cfg["max_eng_chars"] = data["max_eng_chars"]
            extra_allow = data.get("tech_allowlist") or []
            cfg["tech_allowlist"].update(str(x).upper() for x in extra_allow if x)
            custom_map = data.get("custom_translations") or {}
            if isinstance(custom_map, dict):
                custom_pairs = sorted(
                    ((str(k).lower(), str(v)) for k, v in custom_map.items()),
                    key=lambda kv: len(kv[0]),
                    reverse=True,
                )
                raw_terms = custom_pairs + raw_terms
            ws_rules = data.get("workspace_rules") or []
            if isinstance(ws_rules, list):
                cfg["workspace_rules"] = ws_rules
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Ignoring invalid rules config %s: %s", path, exc)

    cfg["semantic_patterns"] = [
        (
            re.compile((r"\b" + re.escape(eng) + r"\b") if eng.isascii() else re.escape(eng), re.IGNORECASE),
            chn,
        )
        for eng, chn in raw_terms
    ]
    return cfg


def decode_varint(data, pos):
    """Decode an unsigned protobuf varint with strict bounds and 64-bit overflow protection."""
    res = 0
    shift = 0
    n = len(data)
    while True:
        if pos >= n or shift > 63:
            raise ValueError("Truncated or oversized varint")
        b = data[pos]
        pos += 1
        res |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return res, pos


def parse_proto(data):
    """Safely parse raw protobuf bytes into (field_num, wire_type, value) tuples."""
    if not isinstance(data, (bytes, bytearray)):
        return []
    pos = 0
    n = len(data)
    fields = []
    while pos < n:
        try:
            tag, pos = decode_varint(data, pos)
            field_num = tag >> 3
            wire_type = tag & 0x07
            if field_num == 0:
                break
            if wire_type == 0:
                val, pos = decode_varint(data, pos)
                fields.append((field_num, wire_type, val))
            elif wire_type == 1:
                if pos + 8 > n:
                    break
                fields.append((field_num, wire_type, data[pos : pos + 8]))
                pos += 8
            elif wire_type == 2:
                length, pos = decode_varint(data, pos)
                if length < 0 or pos + length > n:
                    break
                fields.append((field_num, wire_type, data[pos : pos + length]))
                pos += length
            elif wire_type == 5:
                if pos + 4 > n:
                    break
                fields.append((field_num, wire_type, data[pos : pos + 4]))
                pos += 4
            else:
                break
        except ValueError:
            break
    return fields


def build_local_opener(ctx):
    """Create a proxy-free urllib opener restricted to localhost RPC calls."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ctx),
    )


def _get_loopback_listen_ports(proc):
    """Return listening ports bound strictly to loopback interfaces for the given process."""
    ports = set()
    for conn in proc.net_connections(kind="inet"):
        if (
            conn.status == psutil.CONN_LISTEN
            and conn.laddr
            and conn.laddr.ip in ("127.0.0.1", "::1")
        ):
            ports.add(conn.laddr.port)
    return ports


def discover_language_server_candidates():
    """Discover verified live language_server endpoints from daemon/hub_*.json, with CLI fallback."""
    candidates = []
    seen = set()

    # 1. Primary: daemon/hub_*.json (Antigravity 2.34+), newest first, verified against live PID & loopback socket
    if os.path.isdir(DAEMON_DIR):
        hub_files = sorted(
            glob.glob(os.path.join(DAEMON_DIR, "hub_*.json")),
            key=os.path.getmtime,
            reverse=True,
        )
        for path in hub_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                pid = meta.get("pid")
                token = meta.get("csrfToken")
                https_port = meta.get("httpsPort")
                http_port = meta.get("httpPort")
                if not isinstance(pid, int) or isinstance(pid, bool) or not isinstance(token, str) or not token:
                    continue
                proc = psutil.Process(pid)
                if "language_server" not in (proc.name() or "").lower():
                    continue
                loopback_ports = _get_loopback_listen_ports(proc)
                for scheme, port in (("https", https_port), ("http", http_port)):
                    if (
                        isinstance(port, int)
                        and not isinstance(port, bool)
                        and 1 <= port <= 65535
                        and port in loopback_ports
                    ):
                        key = (pid, scheme, port)
                        if key not in seen:
                            seen.add(key)
                            candidates.append((pid, token, scheme, port))
            except (OSError, ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    # 2. Fallback: legacy CLI --csrf_token (< 2.34)
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info["name"] or "").lower()
            if "language_server" not in name:
                continue
            cmd_str = " ".join(proc.info["cmdline"] or [])
            match = re.search(r"--csrf_token(?:=|\s+)([0-9a-fA-F-]+)", cmd_str)
            if not match:
                continue
            token = match.group(1)
            for port in sorted(_get_loopback_listen_ports(proc)):
                key = (proc.info["pid"], "https", port)
                if key not in seen:
                    seen.add(key)
                    candidates.append((proc.info["pid"], token, "https", port))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return candidates


def probe_language_server(opener):
    """Return (pid, token, base_url) for the first responsive verified language_server."""
    for pid, token, scheme, port in discover_language_server_candidates():
        base_url = f"{scheme}://127.0.0.1:{port}"
        url = f"{base_url}/exa.language_server_pb.LanguageServerService/GetAllCascadeTrajectories"
        headers = {
            "Content-Type": "application/json",
            "x-codeium-csrf-token": token,
            "Connect-Protocol-Version": "1",
        }
        try:
            req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            with opener.open(req, timeout=2) as resp:
                if resp.status == 200:
                    return pid, token, base_url
        except Exception:
            continue
    return None, None, None


def get_user_prompts(cid, max_inputs=4, max_lines=300):
    """Retrieve initial user prompts from transcript on disk without reading multi-MB files in full."""
    if not UUID_RE.fullmatch(cid or "") or not os.path.isdir(BRAIN_DIR):
        return ""
    t_path = os.path.join(BRAIN_DIR, cid, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.isfile(t_path):
        return ""
    prompts = []
    try:
        with open(t_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f):
                if idx >= max_lines:
                    break
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "USER_INPUT":
                    content = data.get("content", "")
                    content = re.sub(r"<[^>]+>", "", content)
                    clean = re.split(
                        r"The current local time is:|The user changed setting|@\[conversation:",
                        content,
                    )[0].strip()
                    if clean:
                        prompts.append(clean)
                    if len(prompts) >= max_inputs:
                        break
    except OSError:
        return ""
    return "\n".join(prompts)


def display_units(text):
    """Compute half-width display units (CJK=2 units, ASCII/other=1 unit)."""
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in text)


def exceeds_sidebar_budget(theme, max_cjk_units=DEFAULT_MAX_CJK_UNITS, max_eng_chars=DEFAULT_MAX_ENG_CHARS):
    """Return True when theme exceeds sidebar width budget."""
    if re.search(r"[\u4e00-\u9fff]", theme):
        return display_units(theme) > max_cjk_units
    return len(theme) > max_eng_chars


def compact_english(text, max_len=DEFAULT_MAX_ENG_CHARS):
    """Compact pure-English titles cleanly at word boundaries to fit <= max_len."""
    if len(text) <= max_len:
        return text
    words = text.split()
    filtered = [w for w in words if w.lower() not in ENGLISH_STOPWORDS] or words
    res = " ".join(filtered)
    if len(res) <= max_len:
        return res
    for pat, rep in ENGLISH_ABBREVS:
        res = pat.sub(rep, res)
    if len(res) <= max_len:
        return res
    words = res.split()
    while len(" ".join(words)) > max_len and len(words) > 1:
        words.pop()
    res = " ".join(words)
    return res[:max_len].strip() if len(res) > max_len else res


def compact_chinese_or_mixed(text, max_units=DEFAULT_MAX_CJK_UNITS):
    """Compact Chinese/mixed titles semantically to fit <= max_units without chopping words."""
    if display_units(text) <= max_units:
        return text
    s = re.sub(r"\b(and|for|the|of|with|to|this)\b", "", text, flags=re.IGNORECASE)
    s = re.sub(r"[与的和及]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if display_units(s) <= max_units:
        return s

    semantic_trims = (
        ("需求设计", "设计"),
        ("进度检查", "进度"),
        ("优惠选择", "优惠"),
        ("安装指南", "安装"),
        ("用法指南", "指南"),
        ("部署指南", "部署"),
        ("安全分析", "分析"),
        ("工具推荐", "工具"),
        ("功能模块", "模块"),
        ("建议助手", "助手"),
        ("比例缩放", "缩放"),
        ("自动确认", ""),
        ("本地安装启动", "装"),
        ("接入", ""),
        ("系统", ""),
        ("选择", ""),
        ("重新", ""),
        ("课程", ""),
        ("功能", ""),
        ("指南", ""),
        ("工具", ""),
    )
    for old, new in semantic_trims:
        if old in s:
            s = s.replace(old, new)
            if display_units(s) <= max_units:
                return s.strip(" -_|｜")

    return s.strip(" -_|｜")


def _has_incomplete_translation(res, allowlist):
    """Return True when Chinese translation left non-allowlisted English words >= 2 chars behind."""
    if not re.search(r"[\u4e00-\u9fff]", res):
        return False
    remaining_words = re.findall(r"[a-zA-Z]{2,}", res)
    return any(w.upper() not in allowlist for w in remaining_words)


def translate_and_compact(raw_title, cfg=None):
    """Translate raw titles cleanly and enforce sidebar budget without mid-word slicing."""
    cfg = cfg or load_rules_config(None)
    max_cjk = cfg["max_cjk_units"]
    max_eng = cfg["max_eng_chars"]
    allowlist = cfg["tech_allowlist"]

    text = re.sub(r"^\d{4}[｜|]\s*", "", (raw_title or "").strip())
    if not text:
        return ""

    if text.isascii() and text.isupper() and len(text) > 4:
        return text if len(text) <= max_eng else compact_english(text, max_eng)

    result = text
    for old, new in PRE_NORMALIZE_RULES:
        result = result.replace(old, new)
    result = re.sub(r"\s+", " ", result).strip()

    for pattern, chn in cfg["semantic_patterns"]:
        result = pattern.sub(chn, result)

    result = re.sub(
        r"(?<=[\u4e00-\u9fff])\s*(?:and|for|to|of|with|the|this)\s*(?=[\u4e00-\u9fff])",
        "",
        result,
        flags=re.IGNORECASE,
    )
    result = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", result)
    result = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", result)
    result = re.sub(r"([a-zA-Z0-9])\s+([\u4e00-\u9fff])", r"\1\2", result)
    result = re.sub(r"([\u4e00-\u9fff])\s+([a-zA-Z0-9])", r"\1\2", result)

    for pattern, acr in COMPILED_ACRONYM_PATTERNS:
        result = pattern.sub(acr, result)

    res = re.sub(r"\s+", " ", result).strip(" ｜|-_:：")
    if not res:
        return compact_english(text, max_eng)

    if re.search(r"[\u4e00-\u9fff]", res):
        if _has_incomplete_translation(res, allowlist) and not re.search(r"[\u4e00-\u9fff]", text):
            return compact_english(text, max_eng)
        return compact_chinese_or_mixed(res, max_cjk)

    return compact_english(res, max_eng)


def needs_upgrade(theme, max_cjk_units=DEFAULT_MAX_CJK_UNITS, max_eng_chars=DEFAULT_MAX_ENG_CHARS):
    """Return True if an existing MMDD theme has broken fragments, raw path slices, or exceeds width budget."""
    if not theme:
        return False
    dirty_tokens = (
        "开发ment", "工具s", "and Benchmarking", "技能Con",
        "UI界面", "缺陷问题", "工作流Protocol", "技能Development", "功能Updates",
    )
    if any(k in theme for k in dirty_tokens):
        return True
    if "\\" in theme or ("/" in theme and not any(k in theme for k in ("CI/CD", "CI|CD", "UI/UX"))):
        return True
    if theme.startswith(("http", "{", "[")):
        return True
    return exceeds_sidebar_budget(theme, max_cjk_units, max_eng_chars)


def match_workspace_rule(proj_info, curr_name, prompt, workspace_rules):
    """Apply optional workspace_rules from rules.json; returns (handled, new_name_or_None)."""
    proj_lower = (proj_info or "").lower()
    name_clean = re.sub(r"^\d{4}[｜|]\s*", "", (curr_name or "")).strip()
    haystack = f"{name_clean} {prompt}".lower()

    for ws in workspace_rules:
        needle = str(ws.get("path_contains") or "").lower()
        if not needle or needle not in proj_lower:
            continue
        skip_pat = ws.get("skip_if_matches")
        if skip_pat and re.match(skip_pat, name_clean, re.IGNORECASE):
            return True, None
        for rule in ws.get("rules") or []:
            triggers = [str(t).lower() for t in (rule.get("match_any") or [])]
            if not any(t in haystack for t in triggers):
                continue
            if "title" in rule:
                return True, str(rule["title"])
            rx = rule.get("regex_extract") or {}
            pat = rx.get("pattern")
            if pat:
                m = re.search(pat, haystack, re.IGNORECASE)
                if m:
                    tpl = str(rx.get("template") or "{0}")
                    for idx, grp in enumerate(m.groups(), start=1):
                        tpl = tpl.replace(f"{{{idx}}}", grp or "")
                    return True, tpl
                if "fallback" in rx:
                    return True, str(rx["fallback"])
        return True, None
    return False, None


def _extract_conversation_record(val):
    """Extract metadata from one protobuf entry safely."""
    sub = parse_proto(val)
    cid = ""
    f2_bytes = b""
    for sf_num, sw_type, sval in sub:
        if sf_num == 1 and sw_type == 2:
            cid = sval.decode("utf-8", errors="ignore")
        elif sf_num == 2 and sw_type == 2:
            f2_bytes = sval

    if not cid or not f2_bytes:
        return None

    title = ""
    annotated_title = ""
    created_sec = 0
    proj_parts = []

    for ff_num, fw_type, fval in parse_proto(f2_bytes):
        if ff_num == 1 and fw_type == 2:
            title = fval.decode("utf-8", errors="ignore")
        elif ff_num == 7 and fw_type == 2:
            for tf_num, tw_type, tval in parse_proto(fval):
                if tf_num == 1 and tw_type == 0:
                    created_sec = tval
        elif ff_num == 15 and fw_type == 2:
            for af_num, aw_type, aval in parse_proto(fval):
                if af_num == 1 and aw_type == 2:
                    annotated_title = aval.decode("utf-8", errors="ignore")
        elif ff_num == 17 and fw_type == 2:
            for pf_num, pw_type, pval in parse_proto(fval):
                if pf_num == 18 and pw_type == 2:
                    proj_parts.append(pval.decode("utf-8", errors="ignore"))
                elif pf_num == 1 and pw_type == 2:
                    for wf_num, ww_type, wval in parse_proto(pval):
                        # Field 3 is a nested proto message; only decode string fields 1 & 2
                        if wf_num in (1, 2) and ww_type == 2:
                            proj_parts.append(wval.decode("utf-8", errors="ignore"))

    return {
        "cid": cid,
        "curr_name": (annotated_title or title or "").strip(),
        "created_sec": created_sec,
        "proj_info": " ".join(proj_parts),
    }


def run_rename_pass(dry_run=False, config_path=None):
    """Execute one rename pass. Returns (renamed_count, skipped_count, ok)."""
    cfg = load_rules_config(config_path)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_local_opener(ctx)

    pid, token, base_url = probe_language_server(opener)
    if not pid or not token or not base_url:
        logger.warning("Language server discovery failed (no verified live hub/CLI endpoint).")
        return 0, 0, False

    if not os.path.exists(PB_PATH):
        logger.warning("Summaries protobuf not found: %s", PB_PATH)
        return 0, 0, False

    try:
        with open(PB_PATH, "rb") as f:
            raw = f.read()
    except OSError as exc:
        logger.error("Failed reading protobuf %s: %s", PB_PATH, exc)
        return 0, 0, False

    headers = {
        "Content-Type": "application/json",
        "x-codeium-csrf-token": token,
        "Connect-Protocol-Version": "1",
    }
    update_url = f"{base_url}/exa.language_server_pb.LanguageServerService/UpdateConversationAnnotations"

    renamed_count = 0
    skipped_count = 0

    for f_num, w_type, val in parse_proto(raw):
        if f_num != 1 or w_type != 2:
            continue
        rec = _extract_conversation_record(val)
        if not rec:
            continue

        cid = rec["cid"]
        curr_name = rec["curr_name"]
        created_sec = rec["created_sec"]
        proj_info = rec["proj_info"]

        if not curr_name or curr_name.lower() in PLACEHOLDER_TITLES:
            skipped_count += 1
            continue

        handled, ws_title = match_workspace_rule(
            proj_info, curr_name, "", cfg["workspace_rules"]
        )
        if handled:
            if not ws_title:
                prompt = get_user_prompts(cid)
                _, ws_title = match_workspace_rule(
                    proj_info, curr_name, prompt, cfg["workspace_rules"]
                )
            if not ws_title or ws_title == curr_name:
                skipped_count += 1
                continue
            new_name = ws_title
        else:
            if created_sec:
                dt = datetime.fromtimestamp(created_sec, tz=cfg["tz"])
                mmdd = dt.strftime("%m%d")
            else:
                mmdd = datetime.now(tz=cfg["tz"]).strftime("%m%d")

            m = re.match(r"^(\d{4})[｜|]\s*(.+)$", curr_name)
            if m:
                existing_mmdd = m.group(1)
                existing_theme = m.group(2).strip()
                if not needs_upgrade(existing_theme, cfg["max_cjk_units"], cfg["max_eng_chars"]):
                    skipped_count += 1
                    continue
                new_theme = translate_and_compact(existing_theme, cfg)
                if not new_theme or new_theme.lower() in ("hi", "hello", ""):
                    skipped_count += 1
                    continue
                new_name = f"{existing_mmdd}｜{new_theme}"
            else:
                new_theme = translate_and_compact(curr_name, cfg)
                if not new_theme or new_theme.lower() in ("hi", "hello", ""):
                    skipped_count += 1
                    continue
                new_name = f"{mmdd}｜{new_theme}"

            if new_name == curr_name:
                skipped_count += 1
                continue

        if dry_run:
            msg = f"[DRY-RUN] '{curr_name}' -> '{new_name}' (ID: {cid[:8]})"
            logger.info(msg)
            if sys.stdout:
                print(msg)
            renamed_count += 1
            continue

        payload = {
            "cascadeIds": [cid],
            "annotations": {"title": new_name},
            "mergeAnnotations": True,
        }
        try:
            req = urllib.request.Request(
                update_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with opener.open(req, timeout=5) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                if resp.status == 200 and '"error"' not in body.lower():
                    logger.info("Renamed: '%s' -> '%s' (ID: %s)", curr_name, new_name, cid[:8])
                    renamed_count += 1
                else:
                    logger.warning("Failed HTTP %s for ID %s: %s", resp.status, cid[:8], body[:200])
        except Exception as exc:
            logger.error("Error updating ID %s: %s", cid[:8], exc)

    if renamed_count > 0:
        logger.info(
            "AutoRename pass completed (dry_run=%s). Renamed: %d, Skipped/Unchanged: %d",
            dry_run,
            renamed_count,
            skipped_count,
        )
    return renamed_count, skipped_count, True


def _get_kernel32():
    """Return kernel32 WinDLL configured with 64-bit-safe HANDLE types and use_last_error."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    return k32


def _acquire_single_instance_mutex():
    """Acquire a Windows Named Mutex to prevent concurrent scheduled/manual executions."""
    if os.name != "nt":
        return None
    k32 = _get_kernel32()
    handle = k32.CreateMutexW(None, False, MUTEX_NAME)
    err = ctypes.get_last_error()
    if handle and err == ERROR_ALREADY_EXISTS:
        k32.CloseHandle(handle)
        return False
    return handle


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auto-rename Antigravity sidebar conversations.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate renames without calling write RPCs.")
    parser.add_argument("--config", help="Optional path to custom rules.json file.")
    args = parser.parse_args(argv)

    mutex = None
    if not args.dry_run:
        mutex = _acquire_single_instance_mutex()
        if mutex is False:
            logger.info("Another AntigravityRenamer instance is already running; exiting.")
            return 0

    try:
        renamed, skipped, ok = run_rename_pass(dry_run=args.dry_run, config_path=args.config)
        if sys.stdout:
            print(f"AutoRename finished (dry_run={args.dry_run}). Renamed: {renamed}, Skipped: {skipped}, OK: {ok}")
        return 0 if ok else 1
    except Exception:
        logger.exception("Unhandled exception during AutoRename pass")
        return 1
    finally:
        if mutex and mutex is not False:
            _get_kernel32().CloseHandle(mutex)


if __name__ == "__main__":
    sys.exit(main())
