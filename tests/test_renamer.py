# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import renamer


class TestProtobufSafety(unittest.TestCase):
    def test_decode_varint_bounds_and_overflow(self):
        with self.assertRaises(ValueError):
            renamer.decode_varint(b"", 0)
        with self.assertRaises(ValueError):
            renamer.decode_varint(b"\x80", 0)
        with self.assertRaises(ValueError):
            renamer.decode_varint(b"\x80" * 11 + b"\x01", 0)

    def test_parse_proto_truncated_and_non_bytes(self):
        self.assertEqual(renamer.parse_proto(b"\x0a\x64ab"), [])
        self.assertEqual(renamer.parse_proto(b"\x09abcd"), [])
        self.assertEqual(renamer.parse_proto(b"\x0dabc"), [])
        self.assertEqual(renamer.parse_proto(12345), [])

    def test_extract_record_ignores_nested_field3_binary(self):
        wf1 = b"\x0a" + bytes([len("file:///e:/Demo")]) + b"file:///e:/Demo"
        wf3 = b"\x1a" + bytes([4]) + b"\x08\x01\x10\x02"
        pf1 = b"\x0a" + bytes([len(wf1 + wf3)]) + wf1 + wf3
        f17 = b"\x8a\x01" + bytes([len(pf1)]) + pf1
        f1 = b"\x0a" + bytes([4]) + b"Test"
        f2 = f1 + f17
        cid = "11111111-1111-1111-1111-111111111111"
        sub = b"\x0a" + bytes([len(cid)]) + cid.encode() + b"\x12" + bytes([len(f2)]) + f2
        rec = renamer._extract_conversation_record(sub)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["curr_name"], "Test")
        self.assertIn("file:///e:/Demo", rec["proj_info"])
        self.assertNotIn("\x08", rec["proj_info"])


class TestServerDiscoveryAndSecurity(unittest.TestCase):
    def test_discover_filters_stale_pid_and_non_loopback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "hub_1000.json"), "w", encoding="utf-8") as f:
                json.dump({"pid": 99999, "httpsPort": 999, "httpPort": 1000, "csrfToken": "tok1"}, f)
            with open(os.path.join(tmp, "hub_2000.json"), "w", encoding="utf-8") as f:
                json.dump({"pid": 222, "httpsPort": 1999, "httpPort": 2000, "csrfToken": "tok2"}, f)
            with open(os.path.join(tmp, "hub_3000.json"), "w", encoding="utf-8") as f:
                json.dump({"pid": 333, "httpsPort": 2999, "httpPort": 3000, "csrfToken": "tok3"}, f)

            class FakeProc:
                def __init__(self, pid):
                    if pid == 99999:
                        raise renamer.psutil.NoSuchProcess(pid)
                    self._pid = pid

                def name(self):
                    return "svchost.exe" if self._pid == 222 else "language_server.exe"

                def net_connections(self, kind="inet"):
                    if self._pid == 333:
                        return [
                            SimpleNamespace(status=renamer.psutil.CONN_LISTEN, laddr=SimpleNamespace(ip="127.0.0.1", port=2999)),
                            SimpleNamespace(status=renamer.psutil.CONN_LISTEN, laddr=SimpleNamespace(ip="0.0.0.0", port=3000)),
                        ]
                    return []

            with mock.patch.object(renamer, "DAEMON_DIR", tmp), \
                 mock.patch.object(renamer.psutil, "Process", side_effect=FakeProc), \
                 mock.patch.object(renamer.psutil, "process_iter", return_value=[]):
                cands = renamer.discover_language_server_candidates()

            self.assertEqual(cands, [(333, "tok3", "https", 2999)])

    def test_build_local_opener_bypasses_proxy(self):
        with mock.patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:9999", "HTTPS_PROXY": "http://127.0.0.1:9999"}):
            opener = renamer.build_local_opener(renamer.ssl.create_default_context())
        proxy_handlers = [h for h in opener.handlers if isinstance(h, renamer.urllib.request.ProxyHandler)]
        self.assertEqual(proxy_handlers, [])


class TestCompactionAndRules(unittest.TestCase):
    def test_sidebar_compaction_chinese_and_english(self):
        cfg = renamer.load_rules_config(None)
        self.assertEqual(
            renamer.translate_and_compact("Project Architecture Review And Enhancement", cfg),
            "项目架构审查完善",
        )
        en = renamer.translate_and_compact("Unknown Library Migration Guide", cfg)
        self.assertLessEqual(len(en), cfg["max_eng_chars"])

        # Mixed CJK + uppercase acronym must never hit ASCII isupper() slice
        mixed = renamer.translate_and_compact("综合整理IT与非IT两份求职简历", cfg)
        self.assertTrue(mixed.endswith("求职简历"))

    def test_custom_rules_json_workspace_and_translations(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "rules.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({
                    "tech_allowlist": ["STRIPE"],
                    "custom_translations": {"stripe integration progress check": "Stripe支付进度"},
                    "workspace_rules": [{
                        "path_contains": "/coursework",
                        "skip_if_matches": "^CourseA-\\d+$",
                        "rules": [{
                            "match_any": ["coursea"],
                            "regex_extract": {"pattern": "week\\s*(\\d+)", "template": "CourseA-{1}", "fallback": "CourseA-Lab"}
                        }]
                    }]
                }, f, ensure_ascii=False)
            cfg = renamer.load_rules_config(cfg_path)
            self.assertEqual(renamer.translate_and_compact("Stripe Integration Progress Check", cfg), "Stripe支付进度")

            handled, title = renamer.match_workspace_rule("file:///e:/Work/coursework", "CourseA Week 4", "", cfg["workspace_rules"])
            self.assertTrue(handled)
            self.assertEqual(title, "CourseA-4")

            handled2, title2 = renamer.match_workspace_rule("file:///e:/Work/coursework", "CourseA-4", "", cfg["workspace_rules"])
            self.assertTrue(handled2)
            self.assertIsNone(title2)

    def test_get_user_prompts_handles_corrupt_tail_and_bad_uuid(self):
        self.assertEqual(renamer.get_user_prompts("../evil"), "")
        with tempfile.TemporaryDirectory() as tmp:
            cid = "11111111-1111-1111-1111-111111111111"
            log_dir = os.path.join(tmp, cid, ".system_generated", "logs")
            os.makedirs(log_dir)
            with open(os.path.join(log_dir, "transcript.jsonl"), "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "USER_INPUT", "content": "Hello world"}) + "\n")
                f.write('{"type": "USER_INPUT", "content": "truncated\n')
            with mock.patch.object(renamer, "BRAIN_DIR", tmp):
                self.assertEqual(renamer.get_user_prompts(cid), "Hello world")

    def test_single_instance_mutex_blocks_reentry(self):
        if os.name != "nt":
            return
        with mock.patch.object(renamer, "MUTEX_NAME", "Local\\TestOpenSourceRenamerMutex"):
            h1 = renamer._acquire_single_instance_mutex()
            self.assertTrue(h1 and h1 is not False)
            try:
                h2 = renamer._acquire_single_instance_mutex()
                self.assertIs(h2, False)
            finally:
                renamer._get_kernel32().CloseHandle(h1)


if __name__ == "__main__":
    unittest.main()
