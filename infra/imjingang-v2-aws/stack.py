from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class ImjingangV2WebStack(cdk.Stack):
    """Separate demo/validation deployment for the V2 OpenAI Realtime app."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        image_tag = cdk.CfnParameter(self, "WebImageTag", type="String", default="v2-realtime-f4e92a7")
        secret_name = cdk.CfnParameter(self, "SecretName", type="String", default="imjingang-v2/openai")
        desired_count = cdk.CfnParameter(self, "DesiredCount", type="Number", default=0, min_value=0, max_value=2)

        repository = ecr.Repository(
            self,
            "WebRepository",
            repository_name="imjingang-v2-web",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        secret = secretsmanager.Secret.from_secret_name_v2(self, "OpenAISecret", secret_name.value_as_string)
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="tasks", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
            ],
        )
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, cluster_name="imjingang-v2")
        log_group = logs.LogGroup(self, "WebLogs", retention=logs.RetentionDays.TWO_WEEKS, removal_policy=cdk.RemovalPolicy.RETAIN)

        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "WebService",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=desired_count.value_as_number,
            public_load_balancer=True,
            listener_port=80,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            assign_public_ip=False,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            max_healthy_percent=200,
            service_name="imjingang-v2-web",
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repository, image_tag.value_as_string),
                container_port=8510,
                container_name="imjingang-v2",
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="v2-web", log_group=log_group),
                secrets={
                    "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(secret, "OPENAI_API_KEY"),
                    "COCKPIT_ACCESS_TOKEN": ecs.Secret.from_secrets_manager(secret, "COCKPIT_ACCESS_TOKEN"),
                },
                environment={
                    "OPENAI_MODEL": "gpt-4.1-mini",
                    "OPENAI_REALTIME_MODEL": "gpt-realtime-2.1",
                    "OPENAI_REALTIME_VOICE": "marin",
                    # The current V2 shell has no account-login screen or seeded
                    # users. Keep the separate validation deployment usable while
                    # retaining the AI access-code gate for OpenAI operations.
                    "V2_REQUIRE_LOGIN": "0",
                    "V2_LOCAL_AI_NO_TOKEN": "0",
                    "V2_SQLITE_PATH": "/tmp/imjingang_v2_demo.db",
                },
            ),
        )
        service.target_group.configure_health_check(
            path="/api/health",
            healthy_http_codes="200",
            interval=cdk.Duration.seconds(30),
            timeout=cdk.Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )

        headers = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeaders",
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
                response_headers_policy=headers,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            comment="HTTPS entry point for Imjingang V2 OpenAI Realtime voice",
        )

        cdk.CfnOutput(self, "RepositoryUri", value=repository.repository_uri)
        cdk.CfnOutput(self, "AlbUrl", value=cdk.Fn.join("", ["http://", service.load_balancer.load_balancer_dns_name]))
        cdk.CfnOutput(self, "CloudFrontUrl", value=cdk.Fn.join("", ["https://", distribution.distribution_domain_name]))
        cdk.CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        cdk.CfnOutput(self, "ServiceName", value=service.service.service_name)
