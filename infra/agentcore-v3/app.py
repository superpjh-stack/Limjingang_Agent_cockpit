#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.agentcore_stack import AgentCoreV3Stack


app = cdk.App(outdir="cdk.out")
AgentCoreV3Stack(
    app,
    "ImjingangAgentCoreV3",
    synthesizer=cdk.DefaultStackSynthesizer(generate_bootstrap_version_rule=False),
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "ap-northeast-2"),
    ),
)
app.synth()
