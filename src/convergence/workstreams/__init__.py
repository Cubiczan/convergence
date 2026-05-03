"""Workstreams public API."""
from convergence.workstreams.base import (
    BaseWorkstream,
    IssueCategory,
    MappingLine,
    MappingType,
    SynergyItem,
    WorkstreamBrief,
    WorkstreamStatus,
)
from convergence.workstreams.coa_mapping import CoAMappingWorkstream
from convergence.workstreams.close_harmonization import CloseHarmonizationWorkstream
from convergence.workstreams.systems_integration import SystemsIntegrationWorkstream
from convergence.workstreams.synergy_tracking import SynergyTrackingWorkstream

WORKSTREAM_MAP = {
    "coa_mapping": CoAMappingWorkstream,
    "close_harmonization": CloseHarmonizationWorkstream,
    "systems_integration": SystemsIntegrationWorkstream,
    "synergy_tracking": SynergyTrackingWorkstream,
}

__all__ = [
    "BaseWorkstream", "CoAMappingWorkstream", "CloseHarmonizationWorkstream",
    "IssueCategory", "MappingLine", "MappingType", "SynergyItem",
    "SynergyTrackingWorkstream", "SystemsIntegrationWorkstream",
    "WORKSTREAM_MAP", "WorkstreamBrief", "WorkstreamStatus",
]
