#!/usr/bin/env bash
# Run from Google Cloud Shell: bash deploy/gcp/deploy.sh YOUR_PROJECT_ID
set -Eeuo pipefail
trap 'echo "部署在第 ${LINENO} 行停止；请处理上方错误后重试。未自动删除任何云资源。" >&2' ERR

PROJECT_ID="${1:-}"
REGION=us-central1
SERVICE=haha-vector-demo
REPOSITORY=haha-vectors
COLLECTION=heritage_catalog_vectors
MARKER=haha-gcp-demo
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

fail() { echo "$*" >&2; exit 1; }
log() { printf '\n%s\n' "$*"; }
[[ "$PROJECT_ID" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || \
  fail "用法：bash deploy/gcp/deploy.sh 实际的GCP项目ID（脚本不创建项目或绑定结算账户）。"
for tool in gcloud python3 curl; do
  command -v "$tool" >/dev/null || fail "缺少 $tool；请在 Google Cloud Shell 执行。"
done
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
[[ -n "$ACTIVE_ACCOUNT" ]] || fail "请先在 Cloud Shell 登录 Google Cloud。"
gcloud projects describe "$PROJECT_ID" --format='value(projectId)' >/dev/null
BILLING="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)')"
[[ "${BILLING,,}" == true ]] || fail "该项目尚未启用结算。请在 Console 绑定结算账户后重试。"

log "预检通过。目标项目：$PROJECT_ID；区域：$REGION；服务：$SERVICE。"
echo "将公开演示应用并使用 Firestore；免费额度超出后可能收费。"
echo "仅上传应用源码、公开演示CSV和图片；LLM、用户分析写入默认关闭。"
TASK_TMP="$(mktemp -d -t haha-gcp.XXXXXXXX)"
trap 'rm -rf -- "$TASK_TMP"' EXIT
python3 deploy/gcp/stage_source.py "$TASK_TMP/source"
# Import and build the same snapshot, even if the original working tree changes.
cd "$TASK_TMP/source"

log "启用部署所需 API"
gcloud services enable run.googleapis.com firestore.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com \
  iam.googleapis.com storage.googleapis.com logging.googleapis.com \
  --project="$PROJECT_ID" --quiet

log "检查 Firestore 默认库；保留已有数据库配置"
gcloud firestore databases list --project="$PROJECT_ID" --format=json > "$TASK_TMP/databases.json"
DB_STATUS="$(python3 - "$TASK_TMP/databases.json" <<'PY'
import json, sys
databases = json.load(open(sys.argv[1]))
if len(databases) > 1:
    raise SystemExit('项目有多个数据库，无法确认默认库享受免费额度；请使用新的专用项目。')
default = next((db for db in databases if db['name'].endswith('/databases/(default)')), None)
if default:
    if default.get('type') != 'FIRESTORE_NATIVE':
        raise SystemExit('已有默认库不是 Firestore Native；请使用新的专用项目。')
    if default.get('databaseEdition', 'STANDARD') != 'STANDARD':
        raise SystemExit('已有默认库不是 Standard；脚本不会更改它。')
    if default.get('locationId') != 'us-central1':
        raise SystemExit('已有默认库不在 us-central1；请使用新的专用项目以匹配部署配置。')
    print('existing')
elif databases:
    raise SystemExit('项目已有其他数据库，新增库可能无免费额度。请使用新的专用项目。')
else:
    print('create')
PY
)"
if [[ "$DB_STATUS" == create ]]; then
  gcloud firestore databases create --project="$PROJECT_ID" --database='(default)' \
    --location="$REGION" --type=firestore-native --edition=standard --quiet
fi

log "配置专用服务身份"
RUNTIME_SA="haha-vector-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA="haha-vector-build@${PROJECT_ID}.iam.gserviceaccount.com"
for account_id in haha-vector-runtime haha-vector-build; do
  account_email="${account_id}@${PROJECT_ID}.iam.gserviceaccount.com"
  existing_name="$(gcloud iam service-accounts list --project="$PROJECT_ID" \
    --filter="email=$account_email" --format='value(displayName)')"
  if [[ -z "$existing_name" ]]; then
    gcloud iam service-accounts create "$account_id" --project="$PROJECT_ID" \
      --display-name="$MARKER" --description="HAHA public catalog demo only" --quiet
  elif [[ "$existing_name" != "$MARKER" ]]; then
    fail "服务账户名称已被其他用途使用：$account_email；未修改该账户。"
  fi
done
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RUNTIME_SA" \
  --role=roles/datastore.viewer --condition=None --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$BUILD_SA" \
  --role=roles/logging.logWriter --condition=None --quiet >/dev/null

log "准备仅用于本应用的镜像仓库和私有构建源存储桶"
repo_description="$(gcloud artifacts repositories list --project="$PROJECT_ID" --location="$REGION" \
  --filter="name=projects/$PROJECT_ID/locations/$REGION/repositories/$REPOSITORY" \
  --format='value(description)')"
if [[ -z "$repo_description" ]]; then
  gcloud artifacts repositories create "$REPOSITORY" --project="$PROJECT_ID" \
    --location="$REGION" --repository-format=docker --description="$MARKER" --quiet
elif [[ "$repo_description" != "$MARKER" ]]; then
  fail "镜像仓库名称已被其他用途使用；未修改它。"
fi
gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" --project="$PROJECT_ID" \
  --location="$REGION" --member="serviceAccount:$BUILD_SA" \
  --role=roles/artifactregistry.writer --quiet >/dev/null
SOURCE_BUCKET="${PROJECT_ID}-haha-build-source"
gcloud storage buckets list --project="$PROJECT_ID" --format=json > "$TASK_TMP/buckets.json"
bucket_status="$(python3 - "$TASK_TMP/buckets.json" "$SOURCE_BUCKET" <<'PY'
import json, sys
bucket = next((b for b in json.load(open(sys.argv[1])) if b.get('name') == sys.argv[2]), None)
if bucket and bucket.get('labels', {}).get('app') != 'haha-gcp-demo':
    raise SystemExit('构建源存储桶名称已被其他用途使用；未修改它。')
print('existing' if bucket else 'create')
PY
)"
if [[ "$bucket_status" == create ]]; then
  gcloud storage buckets create "gs://$SOURCE_BUCKET" --project="$PROJECT_ID" \
    --location="$REGION" --uniform-bucket-level-access --public-access-prevention \
    --soft-delete-duration=0 --labels="app=$MARKER" \
    --lifecycle-file=deploy/gcp/source-lifecycle.json --quiet
fi
gcloud storage buckets add-iam-policy-binding "gs://$SOURCE_BUCKET" --project="$PROJECT_ID" \
  --member="serviceAccount:$BUILD_SA" --role=roles/storage.objectViewer --quiet >/dev/null

log "创建缺失的向量索引，并等待 READY（可能需几分钟）"
python3 deploy/gcp/ensure_indexes.py --project-id "$PROJECT_ID" --collection "$COLLECTION"
log "在独立环境安装运行依赖并导入公开参考目录"
python3 -m venv "$TASK_TMP/venv"
PYTHON="$TASK_TMP/venv/bin/python"
"$PYTHON" -m pip install --disable-pip-version-check -q -e '.[gcp]' 'streamlit==1.59.2'
export VECTOR_BACKEND=firestore GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export FIRESTORE_DATABASE='(default)' VECTOR_COLLECTION="$COLLECTION"
export LLM_ENABLED=false ANALYTICS_ENABLED=false AGENT_REVIEW_MODE_ENABLED=false
"$PYTHON" - <<'PY'
import google.auth
try:
    google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
except google.auth.exceptions.DefaultCredentialsError as exc:
    raise SystemExit('缺少应用默认凭据；运行 gcloud auth application-default login 后重试。') from exc
PY
"$PYTHON" scripts/index_catalog_vectors.py --backend firestore --project-id "$PROJECT_ID"
"$PYTHON" scripts/index_catalog_vectors.py --backend firestore --project-id "$PROJECT_ID" --verify

log "检查目标服务，避免覆盖其他应用"
gcloud run services list --project="$PROJECT_ID" --region="$REGION" --format=json > "$TASK_TMP/services.json"
python3 - "$TASK_TMP/services.json" "$SERVICE" <<'PY'
import json, sys
service = next((s for s in json.load(open(sys.argv[1])) if s.get('metadata', {}).get('name') == sys.argv[2]), None)
if service and service.get('metadata', {}).get('labels', {}).get('app') != 'haha-gcp-demo':
    raise SystemExit('同名 Cloud Run 服务不是本脚本创建的应用，停止以免覆盖。')
PY

log "构建镜像（只上传经过白名单筛选的临时目录）"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/app:$(date -u +%Y%m%d%H%M%S)"
gcloud builds submit "$TASK_TMP/source" --project="$PROJECT_ID" --region="$REGION" \
  --config="$TASK_TMP/source/deploy/gcp/cloudbuild.yaml" \
  --service-account="projects/$PROJECT_ID/serviceAccounts/$BUILD_SA" \
  --gcs-source-staging-dir="gs://$SOURCE_BUCKET/source" \
  --substitutions="_IMAGE_URI=$IMAGE_URI" --quiet

log "部署公开演示服务（无常驻实例；最多一个实例）"
gcloud run deploy "$SERVICE" --project="$PROJECT_ID" --region="$REGION" \
  --image="$IMAGE_URI" --port=8501 --cpu=1 --memory=512Mi \
  --min=0 --max=1 --min-instances=0 --max-instances=1 --concurrency=20 \
  --cpu-throttling --no-cpu-boost --session-affinity --timeout=3600 \
  --service-account="$RUNTIME_SA" --allow-unauthenticated --labels="app=$MARKER" \
  --set-env-vars="VECTOR_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_DATABASE=(default),VECTOR_COLLECTION=$COLLECTION,LLM_ENABLED=false,ANALYTICS_ENABLED=false,AGENT_REVIEW_MODE_ENABLED=false" \
  --quiet
SERVICE_URL="$(gcloud run services describe "$SERVICE" --project="$PROJECT_ID" \
  --region="$REGION" --format='value(status.url)')"
[[ "$SERVICE_URL" == https://* ]] || fail "Cloud Run 未返回有效服务地址。"
log "验证线上健康状态和 Firestore 检索"
curl --fail --silent --show-error --retry 5 --retry-delay 5 --max-time 90 \
  "$SERVICE_URL/_stcore/health"
"$PYTHON" scripts/index_catalog_vectors.py --backend firestore --project-id "$PROJECT_ID" --verify
gcloud artifacts repositories describe "$REPOSITORY" --project="$PROJECT_ID" --location="$REGION" \
  --format='table(name,sizeBytes)'
printf '\n部署并验证完成：%s\n' "$SERVICE_URL"
echo "打开目录页实际搜索一次；长期打开页面会消耗计算额度。"
echo "请在 Billing 设置预算提醒，并查看 docs/GCP_FREE_TIER.md 的用量与清理说明。"
