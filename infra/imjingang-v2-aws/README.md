# 임진강김치 V2 AWS 배포

V3 AgentCore 스택을 건드리지 않고 V2 OpenAI Realtime 앱을 별도 ECS/Fargate + ALB + CloudFront HTTPS 서비스로 배포한다.

배포 순서:

1. Secrets Manager에 `OPENAI_API_KEY`, `COCKPIT_ACCESS_TOKEN` JSON을 `imjingang-v2/openai`로 저장한다.
2. CDK를 `DesiredCount=0`으로 배포해 ECR/VPC/ECS/CloudFront를 만든다.
3. `v2/Dockerfile`을 `linux/amd64`로 빌드해 ECR에 immutable tag로 push한다.
4. CDK를 같은 tag와 `DesiredCount=1`로 업데이트한다.
5. CloudFront URL의 `/api/health`, 기록 조회, 접근 코드·음성 연결을 검증한다.

SQLite 데모 데이터로 동작하는 검증 배포다. 운영 데이터베이스 연결, 조직 SSO, WAF, 비용 알림은 별도 작업이다.
현재 V2 화면에는 업무 계정 로그인 UI가 없으므로 검증 배포는 `V2_REQUIRE_LOGIN=0`으로 기록 조회를 허용한다. OpenAI 호출은 별도의 `COCKPIT_ACCESS_TOKEN`으로 보호된다. 운영 전환 시 조직 SSO와 초기 사용자 프로비저닝을 추가한 뒤 로그인 게이트를 다시 켠다.
