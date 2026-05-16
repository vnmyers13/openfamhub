# Trusting the Caddy Self-Signed Certificate

OpenFamHub uses Caddy as a reverse proxy with automatic HTTPS. On a LAN
without a public domain, Caddy generates a self-signed CA and issues
certificates. Browsers and devices will show a security warning until
the Caddy root certificate is trusted.

## macOS

```sh
# Copy the root cert from the running container
docker compose exec caddy cat /data/caddy/pki/authorities/local/root.crt \
  > /tmp/caddy-root.crt

# Install via Keychain Access
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain /tmp/caddy-root.crt
```

Alternatively, open Keychain Access, drag in `caddy-root.crt`, open it,
expand **Trust**, set **Always Trust**, and close.

## iOS

1. On the server, start a temporary HTTP server in the directory
   containing `caddy-root.crt`:
   ```sh
   docker compose exec caddy cat /data/caddy/pki/authorities/local/root.crt \
     > /tmp/caddy-root.crt
   cd /tmp && python3 -m http.server 8000
   ```
2. On the iOS device, open Safari and navigate to
   `http://<server-ip>:8000/caddy-root.crt`.
3. Tap **Allow** when prompted to download the profile.
4. Open **Settings** → **General** → **VPN & Device Management** → tap the
   Caddy profile → **Install**.
5. Open **Settings** → **General** → **About** → **Certificate Trust
   Settings** → enable full trust for the Caddy root certificate.

## Raspberry Pi OS (Debian / Ubuntu)

```sh
docker compose exec caddy cat /data/caddy/pki/authorities/local/root.crt \
  > /tmp/caddy-root.crt
sudo cp /tmp/caddy-root.crt /usr/local/share/ca-certificates/caddy-root.crt
sudo update-ca-certificates
```

## Android (Chrome)

1. Download `caddy-root.crt` to the device (email it to yourself or use
   the Python HTTP server method above).
2. Open **Settings** → **Security** → **Encryption & credentials** →
   **Install a certificate**.
3. Choose **CA certificate**, then browse to the downloaded file.
4. Reboot the device.
5. Chrome should now trust `https://homehub.local` without warnings.

## Windows

1. Copy `caddy-root.crt` to the Windows machine.
2. Double-click the file → **Install Certificate**.
3. Choose **Local Machine** → **Place all certificates in the following
   store** → **Browse** → **Trusted Root Certification Authorities**.
4. Restart the browser.

## Docker Desktop (macOS / Windows)

If testing only from the host machine, the Caddy root cert is usually
already trusted by the host OS after following the macOS or Windows
steps above. Docker Desktop containers inherit the host CA bundle.

## Verification

After installing, visit `https://homehub.local` — the address bar should
show a padlock with no security warning.
