from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from constructs import Construct


class AgentCoreV3Stack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        model_id = cdk.CfnParameter(self, "BedrockModelId", type="String", description="Bedrock model ID available in this region")
        image_tag = cdk.CfnParameter(self, "RuntimeImageTag", type="String", default="v3")
        voice_image_tag = cdk.CfnParameter(self, "VoiceImageTag", type="String", default="v3-voice")
        text_runtime_arn = cdk.CfnParameter(self, "TextRuntimeArn", type="String", default="unused", description="Existing text Runtime ARN used by the optional voice Runtime")
        enable_runtime = cdk.CfnParameter(self, "EnableAgentCoreRuntime", type="String", default="false", allowed_values=["true", "false"])
        enable_voice = cdk.CfnParameter(self, "EnableVoiceRuntime", type="String", default="false", allowed_values=["true", "false"])
        enable_memory = cdk.CfnParameter(self, "EnableAgentCoreMemory", type="String", default="false", allowed_values=["true", "false"])
        runtime_condition = cdk.CfnCondition(self, "CreateRuntime", expression=cdk.Fn.condition_equals(enable_runtime.value_as_string, "true"))
        voice_condition = cdk.CfnCondition(self, "CreateVoiceRuntime", expression=cdk.Fn.condition_equals(enable_voice.value_as_string, "true"))

        repository = ecr.Repository(
            self,
            "RuntimeRepository",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        web_repository = ecr.Repository(
            self,
            "WebRepository",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        voice_repository = ecr.Repository(
            self,
            "VoiceRepository",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        runtime_role = iam.Role(
            self,
            "RuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Least-privilege role for Imjingang AgentCore V3 Runtime",
        )
        runtime_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                cdk.Fn.sub("arn:${AWS::Partition}:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0"),
                cdk.Fn.sub("arn:${AWS::Partition}:bedrock:${AWS::Region}:${AWS::AccountId}:inference-profile/${Model}", {"Model": model_id.value_as_string}),
            ],
        ))
        repository.grant_pull(runtime_role)

        gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Gateway role for governed V3 runtime access",
        )

        runtime = cdk.CfnResource(
            self,
            "Runtime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeArtifact": {"ContainerConfiguration": {"ContainerUri": cdk.Fn.join("", [repository.repository_uri, ":", image_tag.value_as_string])}},
                "AgentRuntimeName": "ImjingangManufacturingV3",
                "Description": "Read-only evidence-backed kimchi manufacturing agent",
                "EnvironmentVariables": {"AWS_REGION": self.region, "V3_AGENT_BACKEND": "demo", "V3_BEDROCK_MODEL_ID": model_id.value_as_string},
                "LifecycleConfiguration": {"IdleRuntimeSessionTimeout": 900, "MaxLifetime": 28800},
                "NetworkConfiguration": {"NetworkMode": "PUBLIC"},
                "ProtocolConfiguration": "HTTP",
                "RoleArn": runtime_role.role_arn,
                "Tags": {"Application": "imjingang-agentcore-v3", "DataAccess": "read-only"},
            },
        )
        runtime.node.add_dependency(runtime_role)
        runtime.cfn_options.condition = runtime_condition

        endpoint = cdk.CfnResource(
            self,
            "RuntimeEndpoint",
            type="AWS::BedrockAgentCore::RuntimeEndpoint",
            properties={
                "AgentRuntimeId": runtime.get_att("AgentRuntimeId"),
                "AgentRuntimeVersion": runtime.get_att("AgentRuntimeVersion"),
                "Name": "ImjingangV3Live",
                "Description": "Versioned endpoint for Imjingang V3",
                "Tags": {"Application": "imjingang-agentcore-v3"},
            },
        )
        endpoint.node.add_dependency(runtime)
        endpoint.cfn_options.condition = runtime_condition

        voice_role = iam.Role(
            self,
            "VoiceRuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Least-privilege role for Korean bidirectional voice runtime",
        )
        voice_role.add_to_policy(iam.PolicyStatement(
            actions=["transcribe:StartStreamTranscription", "polly:SynthesizeSpeech"],
            resources=["*"],
        ))
        voice_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=[
                text_runtime_arn.value_as_string,
                cdk.Fn.join("", [text_runtime_arn.value_as_string, "/runtime-endpoint/ImjingangV3Live"]),
            ],
        ))
        voice_repository.grant_pull(voice_role)

        voice_runtime = cdk.CfnResource(
            self,
            "VoiceRuntime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeArtifact": {"ContainerConfiguration": {"ContainerUri": cdk.Fn.join("", [voice_repository.repository_uri, ":", voice_image_tag.value_as_string])}},
                "AgentRuntimeName": "ImjingangManufacturingVoiceV3",
                "Description": "Korean streaming voice gateway for the read-only manufacturing agent",
                "EnvironmentVariables": {
                    "AWS_REGION": self.region,
                    "V3_AGENTCORE_RUNTIME_ARN": text_runtime_arn.value_as_string,
                    "V3_AGENTCORE_QUALIFIER": "ImjingangV3Live",
                },
                "LifecycleConfiguration": {"IdleRuntimeSessionTimeout": 900, "MaxLifetime": 28800},
                "NetworkConfiguration": {"NetworkMode": "PUBLIC"},
                "ProtocolConfiguration": "HTTP",
                "RoleArn": voice_role.role_arn,
                "Tags": {"Application": "imjingang-agentcore-v3", "AudioStorage": "disabled", "DataAccess": "read-only"},
            },
        )
        voice_runtime.node.add_dependency(voice_role)
        voice_runtime.cfn_options.condition = voice_condition

        voice_endpoint = cdk.CfnResource(
            self,
            "VoiceRuntimeEndpoint",
            type="AWS::BedrockAgentCore::RuntimeEndpoint",
            properties={
                "AgentRuntimeId": voice_runtime.get_att("AgentRuntimeId"),
                "AgentRuntimeVersion": voice_runtime.get_att("AgentRuntimeVersion"),
                "Name": "ImjingangVoiceV3Live",
                "Description": "Versioned endpoint for Korean realtime voice",
                "Tags": {"Application": "imjingang-agentcore-v3"},
            },
        )
        voice_endpoint.node.add_dependency(voice_runtime)
        voice_endpoint.cfn_options.condition = voice_condition

        gateway = cdk.CfnResource(
            self,
            "Gateway",
            type="AWS::BedrockAgentCore::Gateway",
            properties={
                "Name": "ImjingangV3Gateway",
                "Description": "Governed entry point for the read-only manufacturing runtime",
                "AuthorizerType": "AWS_IAM",
                "RoleArn": gateway_role.role_arn,
                "Tags": {"Application": "imjingang-agentcore-v3", "DataAccess": "read-only"},
            },
        )

        memory_condition = cdk.CfnCondition(self, "CreateMemory", expression=cdk.Fn.condition_equals(enable_memory.value_as_string, "true"))
        memory = cdk.CfnResource(
            self,
            "Memory",
            type="AWS::BedrockAgentCore::Memory",
            properties={
                "Name": "ImjingangV3Memory",
                "Description": "Optional short-lived conversation metadata; no manufacturing source records",
                "EventExpiryDuration": 3,
                "Tags": {"Application": "imjingang-agentcore-v3", "ContainsSourceRecords": "false"},
            },
        )
        memory.cfn_options.condition = memory_condition

        cdk.CfnOutput(self, "RuntimeArn", value=runtime.get_att("AgentRuntimeArn").to_string(), condition=runtime_condition)
        cdk.CfnOutput(self, "RuntimeEndpointArn", value=endpoint.get_att("AgentRuntimeEndpointArn").to_string(), condition=runtime_condition)
        cdk.CfnOutput(self, "GatewayUrl", value=gateway.get_att("GatewayUrl").to_string())
        cdk.CfnOutput(self, "RuntimeRepositoryUri", value=repository.repository_uri)
        cdk.CfnOutput(self, "WebRepositoryUri", value=web_repository.repository_uri)
        cdk.CfnOutput(self, "WebRepositoryName", value=web_repository.repository_name)
        cdk.CfnOutput(self, "VoiceRepositoryUri", value=voice_repository.repository_uri)
        cdk.CfnOutput(self, "VoiceRepositoryName", value=voice_repository.repository_name)
        cdk.CfnOutput(self, "VoiceRuntimeArn", value=voice_runtime.get_att("AgentRuntimeArn").to_string(), condition=voice_condition)
        cdk.CfnOutput(self, "VoiceRuntimeEndpointArn", value=voice_endpoint.get_att("AgentRuntimeEndpointArn").to_string(), condition=voice_condition)
        cdk.CfnOutput(self, "MemoryId", value=memory.get_att("MemoryId").to_string(), condition=memory_condition)
