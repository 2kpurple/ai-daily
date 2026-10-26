#!/usr/bin/env bash
# 日更发布：构建 → 检查 → 提交 → 推送 main
# 需要环境变量 GITHUB_AIDAILY_TOKEN（仅用于本次推送的请求头，不写入任何文件或 git 配置）。
# 用法：./publish.sh [YYYY-MM-DD]      日期省略时取今天（Asia/Taipei）
#       ./publish.sh --dry-run [日期]   只构建、检查并显示将提交的变更，不提交不推送
set -euo pipefail
cd "$(dirname "$0")"

DRY=0
if [[ "${1:-}" == "--dry-run" ]]; then DRY=1; shift; fi
DATE="${1:-$(TZ=Asia/Taipei date +%F)}"
REMOTE="https://github.com/2kpurple/ai-daily.git"

python3 build.py
python3 check.py
python3 -m unittest discover -s tests -q

git add -A
if git diff --cached --quiet; then
  echo "没有变化，无需发布。"
  exit 0
fi
git diff --cached --stat | tail -n 20

if [[ $DRY -eq 1 ]]; then
  git reset -q
  echo "dry-run：以上为将提交的变更，未提交、未推送。"
  exit 0
fi

: "${GITHUB_AIDAILY_TOKEN:?需要环境变量 GITHUB_AIDAILY_TOKEN}"
git -c user.name=2kpurple -c user.email=2kpurple@users.noreply.github.com commit -q -m "更新：${DATE}"
AUTH="$(printf 'x-access-token:%s' "$GITHUB_AIDAILY_TOKEN" | base64 -w0)"
git -c http.extraheader="Authorization: Basic ${AUTH}" push -q "$REMOTE" HEAD:main 2>&1 | sed -E 's/(Basic|token|x-access-token)[^ ]*/\1 ***/g'
unset AUTH
echo "已推送：更新：${DATE}"
