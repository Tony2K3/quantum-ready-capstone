"""Built-in sample data, used when a source has no credentials set. Each set
is in that API's raw shape, so it runs through the same parsing as live
data."""

from __future__ import annotations


def bluedolphin_objects() -> list[dict]:
    """Objects as BlueDolphin's /v1/objects/{id} returns them."""
    def obj(oid, title, type_name, status="", workspace="IT", props=None, rels=None):
        return {
            "id": oid, "object_title": title, "type": {"name": type_name},
            "status": status, "workspace": {"name": workspace},
            "object_properties": [{"name": k, "value": v} for k, v in (props or {}).items()],
            "related_objects": [
                {"object_id": t, "relationship_type": r, "direction": "outgoing"} for t, r in (rels or [])
            ],
        }

    return [
        obj("app-1", "Order Service", "Application Component", "Live", "Sales",
            {"Description": "Takes and tracks customer orders", "Owner": "Commerce team",
             "Lifecycle": "Active", "Business Criticality": "High", "Hosting": "Azure",
             "Vendor": "In-house", "Network Exposure": "Internal"},
            [("do-1", "Access"), ("tc-1", "Realization"), ("cap-1", "Realization"), ("if-1", "Assignment")]),
        obj("app-2", "Payments Gateway", "Application Component", "Live", "Finance",
            {"Description": "Authorizes and settles card payments", "Owner": "Payments team",
             "Lifecycle": "Active", "Business Criticality": "Mission critical",
             "Hosting": "On-premises", "Vendor": "In-house", "Network Exposure": "Partner-facing"},
            [("app-1", "Serving"), ("do-2", "Access"), ("tc-2", "Realization"), ("cap-2", "Realization")]),
        obj("app-3", "Customer Portal", "Application Component", "Live", "Sales",
            {"Description": "Customer-facing web store", "Owner": "Web team", "Lifecycle": "Active",
             "Business Criticality": "High", "Hosting": "AWS", "Vendor": "In-house",
             "Network Exposure": "Internet-facing", "Protocol": "HTTPS"},
            [("app-1", "Flow"), ("do-1", "Access")]),
        obj("app-4", "Inventory API", "Application Component", "Live", "Operations",
            {"Description": "Stock levels for warehouses", "Owner": "Supply chain",
             "Lifecycle": "Phase out", "End of Life": "2027-06-30", "Business Criticality": "Medium",
             "Hosting": "Azure", "Vendor": "In-house", "Network Exposure": "Internal"},
            [("app-1", "Serving"), ("tc-1", "Realization")]),
        obj("do-1", "Customer Record", "Data Object",
            props={"Data Classification": "Confidential", "Owner": "Data governance",
                   "Data Retention": "7 years"}),
        obj("do-2", "Payment Transaction", "Data Object",
            props={"Data Classification": "Restricted", "Owner": "Finance",
                   "Data Retention": "10 years"}),
        obj("do-3", "Product Catalog", "Data Object",
            props={"Data Classification": "Public", "Owner": "Merchandising",
                   "Data Retention": "1 year"}),
        obj("if-1", "Order to Payments API", "Application Interface",
            props={"Description": "REST call to authorize and capture payments", "Protocol": "HTTPS"},
            rels=[("app-2", "Serving"), ("do-2", "Access")]),
        obj("tc-1", "PostgreSQL 14", "System Software",
            props={"Category": "Database", "End of Life": "2026-11-12", "Vendor": "PostgreSQL Global Development Group"}),
        obj("tc-2", "Windows Server 2016", "System Software",
            props={"Category": "Operating system", "End of Life": "2027-01-12", "Vendor": "Microsoft"}),
        obj("cap-1", "Order Management", "Capability"),
        obj("cap-2", "Payment Processing", "Capability"),
    ]


def leanix_fact_sheets() -> list[dict]:
    """Fact sheets as LeanIX's GraphQL allFactSheets query returns them."""
    def rel(*ids):
        return {"edges": [{"node": {"factSheet": {"id": i}}} for i in ids]}

    def lifecycle(current, eol=None):
        phases = [{"phase": "active", "startDate": "2021-01-01"}]
        if eol:
            phases.append({"phase": "endOfLife", "startDate": eol})
        return {"asString": current, "phases": phases}

    def owner(email):
        return {"edges": [{"node": {"type": "RESPONSIBLE", "user": {"email": email}}}]}

    def tags(**groups):
        names = {"hosting": "Hosting Type", "unit": "Business Unit", "exposure": "Network Exposure",
                 "protocol": "Protocol", "retention": "Data Retention"}
        return [{"name": v, "tagGroup": {"name": names[k]}} for k, v in groups.items()]

    return [
        {"id": "lx-app-1", "name": "HR Portal", "type": "Application",
         "description": "Employee self-service", "lifecycle": lifecycle("active"),
         "businessCriticality": "businessOperational",
         "tags": tags(hosting="SaaS", unit="Human Resources", exposure="Internet-facing"),
         "subscriptions": owner("hr-it@example.com"),
         "relToRequires": rel("lx-app-2"), "relApplicationToDataObject": rel("lx-do-1"),
         "relApplicationToBusinessCapability": rel("lx-cap-1"),
         "relConsumerApplicationToInterface": rel("lx-if-1")},
        {"id": "lx-app-2", "name": "Identity Provider", "type": "Application",
         "description": "Single sign-on for internal apps", "lifecycle": lifecycle("active"),
         "businessCriticality": "missionCritical",
         "tags": tags(hosting="On-premises", unit="IT Operations", exposure="Internal"),
         "subscriptions": owner("iam-team@example.com"),
         "relApplicationToITComponent": rel("lx-tc-1"),
         "relApplicationToBusinessCapability": rel("lx-cap-2"),
         "relProviderApplicationToInterface": rel("lx-if-1")},
        {"id": "lx-app-3", "name": "Legacy Payroll", "type": "Application",
         "description": "Mainframe payroll batch", "lifecycle": lifecycle("phaseOut", "2027-12-31"),
         "businessCriticality": "businessCritical",
         "tags": tags(hosting="On-premises", unit="Finance", exposure="Internal", protocol="SFTP"),
         "subscriptions": owner("payroll@example.com"),
         "relToRequires": rel("lx-app-2"), "relApplicationToDataObject": rel("lx-do-1", "lx-do-2"),
         "relApplicationToITComponent": rel("lx-tc-2")},
        {"id": "lx-do-1", "name": "Employee Record", "type": "DataObject",
         "dataClassification": "confidential", "lifecycle": lifecycle("active"),
         "tags": tags(retention="Employment + 7 years")},
        {"id": "lx-do-2", "name": "Payroll Run", "type": "DataObject",
         "dataClassification": "restricted", "lifecycle": lifecycle("active"),
         "tags": tags(retention="10 years")},
        {"id": "lx-if-1", "name": "SSO Login (SAML)", "type": "Interface",
         "description": "Authentication hand-off", "lifecycle": lifecycle("active"),
         "tags": tags(protocol="SAML over HTTPS"),
         "relInterfaceToDataObject": rel("lx-do-1")},
        {"id": "lx-tc-1", "name": "Red Hat Enterprise Linux 8", "type": "ITComponent",
         "category": "operatingSystem", "lifecycle": lifecycle("active", "2029-05-31"),
         "relITComponentToProvider": rel("lx-prov-1")},
        {"id": "lx-tc-2", "name": "IBM z/OS 2.4", "type": "ITComponent",
         "category": "operatingSystem", "lifecycle": lifecycle("phaseOut", "2026-09-30"),
         "relITComponentToProvider": rel("lx-prov-2")},
        {"id": "lx-cap-1", "name": "Workforce Management", "type": "BusinessCapability"},
        {"id": "lx-cap-2", "name": "Identity & Access Management", "type": "BusinessCapability"},
        {"id": "lx-prov-1", "name": "Red Hat", "type": "Provider"},
        {"id": "lx-prov-2", "name": "IBM", "type": "Provider"},
    ]
