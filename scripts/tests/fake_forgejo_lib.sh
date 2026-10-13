# Source from a test harness: start_fake_forgejo <issues.json>; sets $url, $reqlog.
# Needs $tmp and $repo_root. The caller's EXIT trap should run stop_fake_forgejo.
fake_pid=""
start_fake_forgejo() {
    stop_fake_forgejo
    reqlog="$tmp/requests.log"; : > "$reqlog"; rm -f "$tmp/port"
    python3 "$repo_root/scripts/tests/fake_forgejo.py" "$1" "$reqlog" "$tmp/port" & fake_pid=$!
    for _ in $(seq 50); do [ -s "$tmp/port" ] && break; sleep 0.1; done
    [ -s "$tmp/port" ] || { echo "FAIL: fake Forgejo didn't start"; exit 1; }
    url="http://127.0.0.1:$(cat "$tmp/port")"
}
stop_fake_forgejo() { [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; fake_pid=""; return 0; }
