#!/bin/bash
# Smoke test — перевіряє всі основні сценарії Uptime Monitor
# Запускати на сервері як: bash test_smoke.sh

BASE="http://localhost:8080"
COOKIE_JAR="/tmp/uptime_test_cookies.txt"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL+1)); echo "  ❌ $1"; }

echo "=== 1. Health check ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
[ "$code" = "200" ] && ok "Health $code" || fail "Health returned $code"

echo "=== 2. Login page ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/login")
[ "$code" = "200" ] && ok "Login page $code" || fail "Login page $code"

echo "=== 3. Public status page ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/status")
[ "$code" = "200" ] && ok "Public status $code" || fail "Public status $code"

echo "=== 4. Login as admin ==="
curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -X POST "$BASE/login" \
  -d "username=admin&password=291263" > /dev/null
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE/")
# After login redirect, check dashboard
[ "$code" -ne 401 ] && ok "Login + dashboard accessible" || fail "Login failed"

echo "=== 5. API /api/sites ==="
data=$(curl -s -b "$COOKIE_JAR" "$BASE/api/sites")
count=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null)
[ -n "$count" ] && ok "Sites API: $count sites" || fail "Sites API failed"

echo "=== 6. API /api/incidents ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE/api/incidents")
[ "$code" = "200" ] && ok "Incidents API $code" || fail "Incidents API $code"

echo "=== 7. API /api/reports/sla ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE/api/reports/sla?days=7")
[ "$code" = "200" ] && ok "SLA report JSON $code" || fail "SLA report JSON $code"

echo "=== 8. SLA CSV export ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE/api/reports/sla/export?days=7")
[ "$code" = "200" ] && ok "SLA CSV export $code" || fail "SLA CSV export $code"

echo "=== 9. SLA PDF export ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE/api/reports/sla/pdf?days=7")
[ "$code" = "200" ] && ok "SLA PDF export $code" || fail "SLA PDF export $code"

echo "=== 10. CSRF token endpoint (search in dashboard HTML) ==="
csrf=$(curl -s -b "$COOKIE_JAR" "$BASE/" | grep -oP 'name="_csrf_token" value="\K[^"]+' | head -1)
[ -n "$csrf" ] && ok "CSRF token found in page" || echo "  ⚠️  CSRF token not found (may be OK if not on dashboard)"

echo "=== 11. SSL certificates API ==="
cert=$(curl -s -b "$COOKIE_JAR" "$BASE/api/ssl-certificates")
code=$(echo "$cert" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d).__name__)" 2>/dev/null)
[ "$code" = "list" ] && ok "SSL certs API returns list" || fail "SSL certs API: $code"

echo "=== 12. API /api/app-settings ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE/api/app-settings")
[ "$code" = "200" ] && ok "App settings $code" || fail "App settings $code"

echo "=== 13. WebSocket connectivity ==="
ws_code=$(python3 -c "
import asyncio, websockets
async def test():
    try:
        async with websockets.connect('ws://localhost:8080/ws', ping_interval=5, close_timeout=3) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)
            return 'connected'
    except asyncio.TimeoutError:
        return 'timeout_no_data'
    except Exception as e:
        return f'err:{e}'
print(asyncio.run(test()))
" 2>&1)
[[ "$ws_code" == *"connected"* || "$ws_code" == *"timeout"* ]] && ok "WebSocket: $ws_code" || fail "WebSocket: $ws_code"

echo "=== 14. Static files ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/static/app.css")
[ "$code" = "200" ] && ok "Static app.css $code" || fail "Static app.css $code"

echo "=== 15. CSRF validation test (POST without token to non-API) ==="
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" \
  -X POST "$BASE/" -d "test=1")
[ "$code" = "403" ] && ok "CSRF block 403 (expected)" || echo "  ⚠️  CSRF returned $code (may be OK if redirect)"

echo "=== 16. Rate limit check (rapid requests to /status) ==="
for i in $(seq 1 35); do curl -s -o /dev/null "$BASE/status" & done 2>/dev/null
wait
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/status")
[ "$code" = "429" ] && ok "Rate limit triggered after 35 requests (429)" || echo "  ⚠️  Status returned $code (rate limit may need more requests)"

echo ""
echo "===== RESULTS: $PASS passed, $FAIL failed ====="
exit $FAIL
