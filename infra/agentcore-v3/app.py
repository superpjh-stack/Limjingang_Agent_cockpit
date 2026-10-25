#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.agentcore_stack import AgentCoreV3Stack


app = cdk.App()
AgentCoreV3Stack(
    app,
    "ImjingangAgentCoreV3",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "ap-northeast-2"),
    ),
)
app.synth()
