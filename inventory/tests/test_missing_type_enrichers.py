from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

import oci_inventory.enrich.oci_metadata as meta
from oci_inventory.auth.providers import AuthContext
from oci_inventory.enrich import get_enricher_for, is_enricher_registered, set_enrich_context


def _set_dummy_ctx() -> None:
    set_enrich_context(
        AuthContext(
            method="unit",
            config_dict={},
            signer=None,
            profile=None,
            tenancy_ocid="ocid1.tenancy.oc1..aaaa",
        )
    )


def test_dhcpoptions_enricher_accepts_both_casings(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _VcnClient:
        def get_dhcp_options(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_virtual_network_client", lambda ctx, region: _VcnClient())

    for rtype in ("DHCPOptions", "DhcpOptions"):
        enricher = get_enricher_for(rtype)
        res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dhcpoptions.oc1..aaaa"})
        assert res.enrichStatus == "OK"


def test_volume_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _BsClient:
        def get_volume(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_blockstorage_client", lambda ctx, region: _BsClient())

    enricher = get_enricher_for("Volume")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.volume.oc1..aaaa"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["id"] == "ocid1.volume.oc1..aaaa"


def test_private_ip_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _VcnClient:
        def get_private_ip(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_virtual_network_client", lambda ctx, region: _VcnClient())

    enricher = get_enricher_for("PrivateIp")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.privateip.oc1..aaaa"})
    assert res.enrichStatus == "OK"


def test_dns_resolver_and_view_enrichers(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _DnsClient:
        def get_resolver(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "resolver"})

        def get_view(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "view"})

    monkeypatch.setattr(meta.oci_clients, "get_dns_client", lambda ctx, region: _DnsClient())

    r = get_enricher_for("DnsResolver").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dnsresolver.oc1..aaaa"})
    v = get_enricher_for("DnsView").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dnsview.oc1..bbbb"})
    assert r.enrichStatus == "OK"
    assert v.enrichStatus == "OK"


def test_bucket_enricher_uses_namespace_and_display_name(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _ObjClient:
        def get_namespace(self) -> Any:
            return SimpleNamespace(data="myns")

        def get_bucket(self, namespace_name: str, bucket_name: str) -> Any:
            assert namespace_name == "myns"
            assert bucket_name == "my-bucket"
            return SimpleNamespace(data={"namespace": namespace_name, "name": bucket_name})

    monkeypatch.setattr(meta.oci_clients, "get_object_storage_client", lambda ctx, region: _ObjClient())

    enricher = get_enricher_for("Bucket")
    res = enricher.enrich({"region": "mx-queretaro-1", "displayName": "my-bucket"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["name"] == "my-bucket"


def test_log_group_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _LogClient:
        def get_log_group(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_logging_management_client", lambda ctx, region: _LogClient())

    enricher = get_enricher_for("LogGroup")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.loggroup.oc1..aaaa"})
    assert res.enrichStatus == "OK"


def test_log_analytics_entity_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _LaClient:
        def list_namespaces(self, compartment_id: str) -> Any:
            assert compartment_id == "ocid1.tenancy.oc1..aaaa"
            return SimpleNamespace(data=SimpleNamespace(items=[SimpleNamespace(namespace_name="myns")]))

        def get_log_analytics_entity(self, namespace_name: str, log_analytics_entity_id: str) -> Any:
            assert namespace_name == "myns"
            return SimpleNamespace(data={"id": log_analytics_entity_id, "namespace": namespace_name})

    monkeypatch.setattr(meta.oci_clients, "get_log_analytics_client", lambda ctx, region: _LaClient())

    enricher = get_enricher_for("LogAnalyticsEntity")
    res = enricher.enrich(
        {
            "region": "mx-queretaro-1",
            "ocid": "ocid1.loganalyticsentity.oc1..aaaa",
            "compartmentId": "ocid1.compartment.oc1..aaaa",
        }
    )
    assert res.enrichStatus == "OK"


def test_media_services_enrichers(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _MediaClient:
        def get_media_workflow(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "workflow"})

        def get_media_asset(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "asset"})

        def get_stream_cdn_config(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "cdn"})

        def get_stream_distribution_channel(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "dist"})

        def get_stream_packaging_config(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "pkg"})

    monkeypatch.setattr(meta.oci_clients, "get_media_services_client", lambda ctx, region: _MediaClient())

    assert get_enricher_for("MediaWorkflow").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.mediaworkflow.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("MediaAsset").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.mediaasset.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("StreamCdnConfig").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.streamcdnconfig.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("StreamDistributionChannel").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.streamdistributionchannel.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("StreamPackagingConfig").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.streampackagingconfig.oc1..aaaa"}).enrichStatus == "OK"


def test_network_gateway_enrichers(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _VcnClient:
        def get_drg(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_drg_attachment(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_ip_sec_connection(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_virtual_circuit(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_cpe(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_local_peering_gateway(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_remote_peering_connection(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_cross_connect(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_cross_connect_group(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_virtual_network_client", lambda ctx, region: _VcnClient())

    assert get_enricher_for("Drg").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.drg.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("DrgAttachment").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.drgattachment.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("IPSecConnection").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.ipsec.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("VirtualCircuit").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.virtualcircuit.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("Cpe").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.cpe.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("LocalPeeringGateway").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.lpg.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("RemotePeeringConnection").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.rpc.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("CrossConnect").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.crossconnect.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("CrossConnectGroup").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.crossconnectgroup.oc1..aaaa"}).enrichStatus == "OK"


def test_firewall_and_waf_enrichers(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _FirewallClient:
        def get_network_firewall(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_network_firewall_policy(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    class _WafClient:
        def get_web_app_firewall(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

        def get_web_app_firewall_policy(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_network_firewall_client", lambda ctx, region: _FirewallClient())
    monkeypatch.setattr(meta.oci_clients, "get_waf_client", lambda ctx, region: _WafClient())

    assert get_enricher_for("NetworkFirewall").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.networkfirewall.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("NetworkFirewallPolicy").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.networkfirewallpolicy.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("WebAppFirewall").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.webappfirewall.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("WebAppFirewallPolicy").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.webappfirewallpolicy.oc1..aaaa"}).enrichStatus == "OK"


def test_load_balancer_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _LbClient:
        def get_load_balancer(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_load_balancer_client", lambda ctx, region: _LbClient())

    res = get_enricher_for("LoadBalancer").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.loadbalancer.oc1..aaaa"})
    assert res.enrichStatus == "OK"


def test_missing_resource_type_enrichers_are_registered() -> None:
    expected = {
        "AgcsGovernanceInstance",
        "AiDataPlatform",
        "AiLanguageProject",
        "AiVisionModel",
        "AiVisionProject",
        "Alarm",
        "AnalyticsInstance",
        "ApiDeployment",
        "ApiGateway",
        "ApiGatewayApi",
        "App",
        "AutonomousDatabase",
        "BootVolumeBackup",
        "Budget",
        "Certificate",
        "CertificateAuthority",
        "CloudGuardDetectorRecipe",
        "CloudGuardManagedList",
        "CloudGuardResponderRecipe",
        "CloudGuardSavedQuery",
        "ClustersCluster",
        "Compartment",
        "ConnectHarness",
        "ConsoleDashboard",
        "ConsoleDashboardGroup",
        "Container",
        "ContainerImage",
        "ContainerInstance",
        "ContainerRepo",
        "DISWorkspace",
        "DataFlowApplication",
        "DataFlowRun",
        "DataLabelingDataset",
        "DataSafeAuditProfile",
        "DataSafeReportDefinition",
        "DataSafeSecurityAssessment",
        "DataSafeUserAssessment",
        "DataScienceJob",
        "DataScienceJobRun",
        "DataScienceModel",
        "DataScienceModelDeployment",
        "DataScienceModelVersionSet",
        "DataScienceNotebookSession",
        "DataScienceProject",
        "DatabaseToolsPrivateEndpoint",
        "DbNode",
        "DedicatedVmHost",
        "DevOpsBuildPipelineStage",
        "DevOpsBuildRun",
        "DevOpsDeployArtifact",
        "DevOpsProject",
        "DevOpsRepository",
        "DrgRouteDistribution",
        "DrgRouteTable",
        "DynamicResourceGroup",
        "EmailDkim",
        "EmailDomain",
        "EmailSender",
        "EventRule",
        "Famsplatformconfiguration",
        "FileSystem",
        "FunctionsApplication",
        "FunctionsFunction",
        "GenAiAgent",
        "GenAiAgentDataIngestionJob",
        "GenAiAgentDataSource",
        "GenAiAgentEndpoint",
        "GenAiAgentKnowledgeBase",
        "Group",
        "HttpRedirect",
        "IdentityProvider",
        "IntegrationInstance",
        "Key",
        "KmsHsmCluster",
        "KmsHsmPartition",
        "Log",
        "LogSavedSearch",
        "ManagementAgentInstallKey",
        "MysqlBackup",
        "MysqlDbSystem",
        "OdaInstance",
        "OnsSubscription",
        "OnsTopic",
        "OrmConfigSourceProvider",
        "OrmJob",
        "OrmPrivateEndpoint",
        "OrmStack",
        "OrmTemplate",
        "OsmhLifecycleEnvironment",
        "OsmhManagedInstanceGroup",
        "OsmhProfile",
        "OsmhScheduledJob",
        "OsmhSoftwareSource",
        "PathAnalyzerTest",
        "PluggableDatabase",
        "PostgresqlConfiguration",
        "ProtectedDatabase",
        "RecoveryServiceSubnet",
        "ResourceSchedule",
        "SecurityAttributeNamespace",
        "SecurityZonesSecurityRecipe",
        "SecurityZonesSecurityZone",
        "ServiceConnector",
        "Stream",
        "TagDefault",
        "TagNamespace",
        "User",
        "VaultSecret",
        "VisualBuilderInstance",
        "VolumeBackup",
        "VolumeBackupPolicy",
        "VolumeGroup",
        "VolumeGroupBackup",
        "VssHostScanRecipe",
        "VssHostScanTarget",
        "WaasCertificate",
        "ZprPolicy",
    }

    missing = [rtype for rtype in expected if not is_enricher_registered(rtype)]
    assert not missing, f"Missing enricher registrations: {missing}"
