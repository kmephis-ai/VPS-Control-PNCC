import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".pncc-dev/scripts/invoke_wave6_wu149_workflow_dispatch.ps1"
CONTRACT = ROOT / ".pncc-dev/contracts/wave6-wu151-owner-operated-workflow-dispatch-bridge.json"


class Wu151OwnerOperatedDispatchBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.lower = cls.script.lower()
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_exactly_bounded_to_wu149_fallback(self):
        target = self.contract["target"]
        self.assertEqual(target["workflow_file"], ".github/workflows/wave6-wu149-bounded-dispatch-fallback.yml")
        self.assertEqual(target["dispatch_ref"], "main")
        self.assertEqual(target["required_event"], "workflow_dispatch")
        self.assertEqual(target["required_runner_label"], "ubuntu-24.04")

    def test_only_dispatch_invocation_authority_is_granted(self):
        authority = self.contract["authority"]
        self.assertTrue(authority["workflow_dispatch_invocation_authority"])
        for key, value in authority.items():
            if key != "workflow_dispatch_invocation_authority":
                self.assertFalse(value, key)

    def test_script_has_one_post_and_it_is_exact_dispatch_endpoint(self):
        self.assertEqual(self.script.count("'POST'"), 1)
        self.assertIn("$dispatchEndpoint", self.script)
        self.assertIn("actions/workflows/$WorkflowFile/dispatches", self.script)
        self.assertIn("$WorkflowFile = 'wave6-wu149-bounded-dispatch-fallback.yml'", self.script)

    def test_script_uses_existing_gh_auth_without_extracting_credentials(self):
        self.assertIn("gh auth status --hostname github.com", self.script)
        forbidden = [
            "gh auth token",
            "gh_token",
            "github_token",
            "authorization: bearer",
            "authorization: token",
            "--with-token",
            "personal_access_token",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, self.lower, needle)

    def test_script_has_no_trigger_proxy_or_alternate_dispatch(self):
        forbidden = [
            "repository_dispatch",
            "gh workflow run",
            "/dispatches -f event_type",
            "issue_comment",
            "workflow_run",
            "schedule:",
            "cron:",
            "webhook",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, self.lower, needle)

    def test_script_has_no_repository_write_path(self):
        forbidden = [
            "git push",
            "git commit",
            "git tag",
            "update-ref",
            "contents/",
            "pulls/",
            "issues/",
            "releases",
            "--force",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, self.lower, needle)

    def test_fresh_main_is_read_before_and_after_dispatch(self):
        self.assertIn("$mainBefore = Invoke-GhApiJson", self.script)
        self.assertIn("$mainAfter = Invoke-GhApiJson", self.script)
        self.assertIn("$postDispatchMainSha -ceq $expectedMainSha", self.script)
        self.assertLess(self.script.index("$mainBefore ="), self.script.index("$dispatch ="))
        self.assertLess(self.script.index("$dispatch ="), self.script.index("$mainAfter ="))

    def test_dispatch_response_must_identify_exact_run(self):
        self.assertIn("$dispatch.workflow_run_id", self.script)
        self.assertIn("[Int64]$run.id -eq $runId", self.script)
        self.assertIn("[string]$run.event -ceq 'workflow_dispatch'", self.script)
        self.assertIn("[string]$run.head_sha -ceq $expectedMainSha", self.script)
        self.assertIn("[string]$run.path -ceq $WorkflowPath", self.script)

    def test_github_hosted_runner_is_proven_fail_closed(self):
        self.assertIn("$labels -notcontains 'self-hosted'", self.script)
        self.assertIn("$labels -contains $RequiredRunnerLabel", self.script)
        self.assertEqual(self.contract["target"]["required_runner_label"], "ubuntu-24.04")

    def test_polling_is_bounded(self):
        self.assertIn("$TimeoutSeconds -ge 30 -and $TimeoutSeconds -le 1800", self.script)
        self.assertIn("$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)", self.script)
        self.assertIn("did not reach a terminal state before timeout", self.script)

    def test_no_runtime_or_protected_tunnel_surface(self):
        for needle in ["127.0.0.1:1080", "127.0.0.1:1081", "v6.3.1", "proxifier", "putty", "plink"]:
            self.assertNotIn(needle, self.lower, needle)

    def test_claims_do_not_overstate_scheduler_repair(self):
        claims = self.contract["claims"]
        self.assertFalse(claims["repairs_github_schedule_delivery"])
        self.assertFalse(claims["replaces_wu137_or_wu144"])
        self.assertFalse(claims["creates_automatic_scheduler"])
        self.assertFalse(claims["adds_new_trigger"])
        self.assertIn("scheduler_delivery_repaired = $false", self.script)
        self.assertIn("automatic_scheduler_replacement = $false", self.script)

    def test_contract_requires_exact_provider_proof(self):
        protocol = self.contract["dispatch_protocol"]
        required_true = [
            "fresh_main_read_before_dispatch",
            "fresh_main_read_after_dispatch",
            "require_main_unchanged_across_dispatch",
            "require_dispatch_response_run_id",
            "require_exact_run_head_sha",
            "require_exact_workflow_path",
            "require_event_workflow_dispatch",
            "require_github_hosted_runner_proof",
            "fail_closed_on_ambiguous_or_unprovable_provider_state",
        ]
        for key in required_true:
            self.assertTrue(protocol[key], key)


if __name__ == "__main__":
    unittest.main()
