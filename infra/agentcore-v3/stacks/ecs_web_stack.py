from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct


class EcsWebV3Stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repository_name = cdk.CfnParameter(self, "WebRepositoryName", type="String")
        image_tag = cdk.CfnParameter(self, "WebImageTag", type="String", default="v3-web")
        runtime_arn = cdk.CfnParameter(self, "AgentRuntimeArn", type="String")
        runtime_qualifier = cdk.CfnParameter(self, "AgentRuntimeQualifier", type="String", default="ImjingangV3Live")
        voice_runtime_arn = cdk.CfnParameter(self, "VoiceRuntimeArn", type="String")
        voice_runtime_qualifier = cdk.CfnParameter(self, "VoiceRuntimeQualifier", type="String", default="ImjingangVoiceV3Live")
        gateway_url = cdk.CfnParameter(self, "AgentCoreGatewayUrl", type="String")
        model_id = cdk.CfnParameter(self, "BedrockModelId", type="String", default="global.amazon.nova-2-lite-v1:0")

        repository = ecr.Repository.from_repository_name(self, "WebRepository", repository_name.value_as_string)
        vpc = ec2.Vpc(
            self,
            "Vpc",
            availability_zones=["ap-northeast-2a", "ap-northeast-2c"],
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="tasks", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
            ],
        )
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, cluster_name="imjingang-agentcore-v3")
        log_group = logs.LogGroup(
            self,
            "WebLogs",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Least-privilege role for V3 web to invoke AgentCore Runtime",
        )
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=[
                runtime_arn.value_as_string,
                cdk.Fn.join("", [runtime_arn.value_as_string, "/runtime-endpoint/", runtime_qualifier.value_as_string]),
            ],
        ))
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream"],
            resources=[
                voice_runtime_arn.value_as_string,
                cdk.Fn.join("", [voice_runtime_arn.value_as_string, "/runtime-endpoint/DEFAULT"]),
                cdk.Fn.join("", [voice_runtime_arn.value_as_string, "/runtime-endpoint/", voice_runtime_qualifier.value_as_string]),
            ],
        ))
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            cpu=256,
            memory_limit_mib=512,
            task_role=task_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        container = task_definition.add_container(
            "Web",
            image=ecs.ContainerImage.from_ecr_repository(repository, image_tag.value_as_string),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="web", log_group=log_group),
            environment={
                "V3_AGENT_BACKEND": "agentcore",
                "AWS_REGION": self.region,
                "V3_BEDROCK_MODEL_ID": model_id.value_as_string,
                "V3_AGENTCORE_RUNTIME_ARN": runtime_arn.value_as_string,
                "V3_AGENTCORE_QUALIFIER": runtime_qualifier.value_as_string,
                "V3_AGENTCORE_GATEWAY_URL": gateway_url.value_as_string,
                "V3_VOICE_ENABLED": "1",
                "V3_VOICE_RUNTIME_ARN": voice_runtime_arn.value_as_string,
                "V3_VOICE_RUNTIME_QUALIFIER": voice_runtime_qualifier.value_as_string,
                "V3_VOICE_URL_TTL_SECONDS": "60",
                "V3_REQUEST_TIMEOUT": "120",
                "V3_SECURE_COOKIE": "1",
                "V3_SQLITE_PATH": "/tmp/imjingang_v3_demo.db",
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8510/api/health', timeout=4)\" || exit 1"],
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(5),
                retries=3,
                start_period=cdk.Duration.seconds(30),
            ),
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8510, protocol=ecs.Protocol.TCP))

        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "WebService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            assign_public_ip=False,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            max_healthy_percent=200,
            service_name="imjingang-agentcore-v3-web",
        )
        service.target_group.configure_health_check(
            path="/api/health",
            healthy_http_codes="200",
            interval=cdk.Duration.seconds(30),
            timeout=cdk.Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )

        response_headers = cloudfront.ResponseHeadersPolicy(
            self,
            "VoiceSecurityHeaders",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(frame_option=cloudfront.HeadersFrameOption.DENY, override=True),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(referrer_policy=cloudfront.HeadersReferrerPolicy.SAME_ORIGIN, override=True),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(access_control_max_age=cdk.Duration.days(365), include_subdomains=True, override=True),
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[cloudfront.ResponseCustomHeader(header="Permissions-Policy", value="microphone=(self)", override=True)]
            ),
        )
        distribution = cloudfront.Distribution(
            self,
            "WebDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(service.load_balancer, protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY),
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                response_headers_policy=response_headers,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            comment="HTTPS entry point for Imjingang V3 text and realtime voice",
        )

        cdk.CfnOutput(self, "EcsWebUrl", value=cdk.Fn.join("", ["http://", service.load_balancer.load_balancer_dns_name]))
        cdk.CfnOutput(self, "EcsClusterName", value=cluster.cluster_name)
        cdk.CfnOutput(self, "EcsServiceName", value=service.service.service_name)
        cdk.CfnOutput(self, "AlbDnsName", value=service.load_balancer.load_balancer_dns_name)
        cdk.CfnOutput(self, "EcsWebHttpsUrl", value=cdk.Fn.join("", ["https://", distribution.distribution_domain_name]))
