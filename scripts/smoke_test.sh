#!/usr/bin/env bash
set -euo pipefail

if [[ "${RUN_SMOKE:-0}" != "1" ]]; then
  echo "RUN_SMOKE is not 1; skipping cloud smoke test."
  exit 0
fi

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
SMOKE_AUDIO_EN="${SMOKE_AUDIO_EN:-}"
SMOKE_AUDIO_ZH="${SMOKE_AUDIO_ZH:-}"
SMOKE_BATCH_URLS="${SMOKE_BATCH_URLS:-}"

if [[ -z "$SMOKE_AUDIO_EN" || ! -f "$SMOKE_AUDIO_EN" ]]; then
  echo "SMOKE_AUDIO_EN must point to a 1-2 minute mp3/m4a/wav fixture."
  exit 2
fi

curl -fsS "$BASE_URL/api/health" >/dev/null

submit_file() {
  local audio_path="$1"
  curl -fsS \
    -F source_type=local_file \
    -F "file=@${audio_path}" \
    "$BASE_URL/api/episodes"
}

wait_job() {
  local job_id="$1"
  python - "$BASE_URL" "$job_id" <<'PY'
import json
import sys
import time
import urllib.request

base_url, job_id = sys.argv[1], sys.argv[2]
deadline = time.monotonic() + 900
while time.monotonic() < deadline:
    with urllib.request.urlopen(f"{base_url}/api/jobs/{job_id}") as response:
        payload = json.load(response)
    if payload["state"] in {"done", "partial", "failed"}:
        print(json.dumps(payload))
        sys.exit(0 if payload["state"] in {"done", "partial"} else 1)
    time.sleep(2)
raise SystemExit("job did not finish before timeout")
PY
}

json_field() {
  python -c "import json,sys; print(json.load(sys.stdin)$1)"
}

created="$(submit_file "$SMOKE_AUDIO_EN")"
episode_id="$(printf '%s' "$created" | json_field "['episode']['id']")"
job_id="$(printf '%s' "$created" | json_field "['job']['id']")"
wait_job "$job_id" >/dev/null

detail="$(curl -fsS "$BASE_URL/api/episodes/$episode_id")"
python - "$detail" <<'PY'
import json
import sys

detail = json.loads(sys.argv[1])
assert detail["hook"] and len(detail["hook"]) <= 50
assert detail["three_act"]
assert detail["chapters"] is not None
PY

curl -fsS "$BASE_URL/api/episodes/$episode_id/files/markdown" >/dev/null
curl -fsS "$BASE_URL/api/episodes/$episode_id/files/json" >/dev/null
curl -fsS -H "Range: bytes=0-3" "$BASE_URL/api/episodes/$episode_id/files/audio" >/dev/null

if [[ -n "$SMOKE_AUDIO_ZH" && -f "$SMOKE_AUDIO_ZH" ]]; then
  zh_created="$(submit_file "$SMOKE_AUDIO_ZH")"
  zh_job_id="$(printf '%s' "$zh_created" | json_field "['job']['id']")"
  wait_job "$zh_job_id" >/dev/null
fi

curl -fsS -X POST "$BASE_URL/api/episodes/$episode_id/digest" >/dev/null
sleep 2

if [[ -n "$SMOKE_BATCH_URLS" && -f "$SMOKE_BATCH_URLS" ]]; then
  python - "$BASE_URL" "$SMOKE_BATCH_URLS" <<'PY'
import json
import sys
import urllib.request

base_url, urls_path = sys.argv[1], sys.argv[2]
items = [{"source_type": "direct_url", "source_ref": line.strip()} for line in open(urls_path) if line.strip()]
request = urllib.request.Request(
    f"{base_url}/api/episodes/batch",
    data=json.dumps({"items": items}).encode(),
    headers={"content-type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    print(response.read().decode())
PY
fi

make verify-quotes

curl -fsS -X DELETE "$BASE_URL/api/episodes/$episode_id" >/dev/null
echo "Smoke test completed."
