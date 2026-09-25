"""Provision an account without exposing passwords in command arguments."""
import argparse
import getpass
import os
from pathlib import Path

from dotenv import load_dotenv
from imjingang_agent.data_hub import create_repository
from v2.work import WorkStore


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    parser = argparse.ArgumentParser(description='V2 업무 계정 생성')
    parser.add_argument('username')
    parser.add_argument('--name', required=True)
    parser.add_argument('--organization', default='imjingang')
    parser.add_argument('--role', choices=['operator', 'reviewer', 'admin'], default='operator')
    args = parser.parse_args()
    password = getpass.getpass('비밀번호 (12자 이상): ')
    if password != getpass.getpass('비밀번호 확인: '):
        raise SystemExit('비밀번호가 일치하지 않습니다.')
    repo = create_repository(os.getenv('V2_SQLITE_PATH', 'data/imjingang_v2_demo.db'))
    WorkStore(repo).add_user(args.username, args.name, args.organization, args.role, password)
    print('계정이 생성되었습니다. 업무 화면에서 로그인하세요.')


if __name__ == '__main__':
    main()
