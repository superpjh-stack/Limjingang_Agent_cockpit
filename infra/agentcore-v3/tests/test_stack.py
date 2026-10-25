import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from stacks.agentcore_stack import AgentCoreV3Stack


def template():
    app = cdk.App()
    return Template.from_stack(AgentCoreV3Stack(app, "TestStack", env=cdk.Environment(account="123456789012", region="ap-northeast-2")))


def test_runtime_gateway_and_optional_memory_are_declared():
    result = template()
    result.resource_count_is("AWS::BedrockAgentCore::Runtime", 1)
    result.resource_count_is("AWS::BedrockAgentCore::RuntimeEndpoint", 1)
    result.resource_count_is("AWS::BedrockAgentCore::Gateway", 1)
    result.resource_count_is("AWS::BedrockAgentCore::Memory", 1)
    result.has_condition("CreateRuntime", {"Fn::Equals": [{"Ref": "EnableAgentCoreRuntime"}, "true"]})


def test_runtime_is_http_read_only_and_memory_expires_at_service_minimum():
    result = template()
    result.has_resource_properties("AWS::BedrockAgentCore::Runtime", {"ProtocolConfiguration": "HTTP", "LifecycleConfiguration": {"MaxLifetime": 28800}, "Tags": {"DataAccess": "read-only"}})
    result.has_resource_properties("AWS::BedrockAgentCore::Gateway", {"AuthorizerType": "AWS_IAM"})
    result.has_resource_properties("AWS::BedrockAgentCore::Memory", {"EventExpiryDuration": 3})
    result.has_resource_properties("AWS::IAM::Policy", {"PolicyDocument": {"Statement": Match.array_with([Match.object_like({"Action": Match.array_with(["bedrock:InvokeModel"]), "Effect": "Allow", "Resource": Match.array_with([Match.object_like({"Fn::Sub": "arn:${AWS::Partition}:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0"})])})])}})
