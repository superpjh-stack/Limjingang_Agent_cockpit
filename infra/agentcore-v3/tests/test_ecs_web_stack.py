import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from stacks.ecs_web_stack import EcsWebV3Stack


def template():
    app = cdk.App()
    stack = EcsWebV3Stack(app, "EcsTest", env=cdk.Environment(account="123456789012", region="ap-northeast-2"))
    return Template.from_stack(stack)


def test_web_service_is_private_fargate_behind_public_alb():
    result = template()
    result.has_resource_properties("AWS::EC2::Subnet", {"AvailabilityZone": "ap-northeast-2a"})
    result.has_resource_properties("AWS::EC2::Subnet", {"AvailabilityZone": "ap-northeast-2c"})
    result.resource_count_is("AWS::ECS::Service", 1)
    result.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 1)
    result.resource_count_is("AWS::CloudFront::Distribution", 1)
    result.has_resource_properties("AWS::ECS::Service", {
        "DesiredCount": 1,
        "DeploymentConfiguration": Match.object_like({"DeploymentCircuitBreaker": {"Enable": True, "Rollback": True}}),
        "NetworkConfiguration": {"AwsvpcConfiguration": Match.object_like({"AssignPublicIp": "DISABLED"})},
    })
    result.has_resource_properties("AWS::ElasticLoadBalancingV2::TargetGroup", {
        "HealthCheckPath": "/api/health",
        "Port": 80,
        "TargetType": "ip",
    })


def test_task_uses_amd64_web_image_and_minimum_agentcore_permission():
    result = template()
    result.has_resource_properties("AWS::ECS::TaskDefinition", {
        "Cpu": "256",
        "Memory": "512",
        "RuntimePlatform": {"CpuArchitecture": "X86_64", "OperatingSystemFamily": "LINUX"},
        "ContainerDefinitions": Match.array_with([Match.object_like({
            "PortMappings": Match.array_with([Match.object_like({"ContainerPort": 8510})]),
            "Environment": Match.array_with([
                {"Name": "V3_AGENT_BACKEND", "Value": "agentcore"},
                {"Name": "V3_AGENTCORE_QUALIFIER", "Value": {"Ref": "AgentRuntimeQualifier"}},
                {"Name": "V3_VOICE_ENABLED", "Value": "1"},
                {"Name": "V3_SECURE_COOKIE", "Value": "1"},
            ]),
        })]),
    })
    result.has_resource_properties("AWS::IAM::Policy", {
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Action": "bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream",
            "Effect": "Allow",
        })])},
    })
    result.has_resource_properties("AWS::IAM::Policy", {
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Action": "bedrock-agentcore:InvokeAgentRuntime",
            "Effect": "Allow",
            "Resource": [
                {"Ref": "AgentRuntimeArn"},
                {"Fn::Join": ["", [{"Ref": "AgentRuntimeArn"}, "/runtime-endpoint/", {"Ref": "AgentRuntimeQualifier"}]]},
            ],
        })])},
    })
