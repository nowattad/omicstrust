from __future__ import annotations

from omicstrust.copilot.schemas import CopilotPlan, WorkflowRoute
from omicstrust.copilot.safety import is_supported_workflow
from omicstrust.copilot.workflow_registry import route_action_for_workflow


def route_workflow(plan: CopilotPlan) -> WorkflowRoute:
    if plan.status in {"rejected", "needs_clarification", "missing_inputs", "unsupported_workflow", "unsupported_request"}:
        return WorkflowRoute(plan.workflow, "none", False, plan.reason or plan.status)
    if not is_supported_workflow(plan.workflow):
        return WorkflowRoute(plan.workflow, "none", False, "workflow_not_allowlisted")
    action = route_action_for_workflow(plan.workflow)
    if not action:
        return WorkflowRoute(plan.workflow, "none", False, "workflow_not_registered")
    return WorkflowRoute(plan.workflow, action, True)
