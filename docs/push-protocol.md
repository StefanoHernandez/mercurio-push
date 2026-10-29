# Mercurio push: wire protocol v1

Notifications that reach the phone when it can't reach the gateway (off the tailnet, on mobile data). The
gateway runs the **mercurio-push** Hermes plugin. The gateway and the phone talk through an **ntfy** server
(public `https://ntfy.sh` by default, the user's own instance, or a **UnifiedPush** distributor URL), and both
connect **outbound**. Everything is end-to-end encrypted and signed, so the push server only carries opaque
envelopes.

This document extends [Herald's push protocol v1](https://github.com/Giton22/herald/blob/master/docs/push-protocol.md)
with Mercurio's optional `push_endpoint` field. Crypto domain strings remain **`herald-push/v1`** (HKDF info
and signed-message prefix) for byte compatibility with the Mercurio app build tested against Giton22's
hermes-herald-push at `c88f027`.

## Keys and topics

At registration each side holds two P-256 key pairs:

| Key | Use |
|---|---|
| `enc` | ECDH: the other side encrypts to it |
| `sig` | ECDSA P-256/SHA-256: this side signs what it sends |

- The **phone** generates its pairs once. Private keys stay on the phone (AndroidKeyStore-wrapped on Android).
- The **gateway** generates its pairs once in `<hermes root>/plugin-data/mercurio-push/identity.json` (mode 0600).
- **`push_topic`** (gateway → phone) and **`reply_topic`** (phone → gateway, reserved) are each `hp-` plus 32
  hex characters (128 random bits). They stay **required** at registration even when UnifiedPush is used.
- Optional **`push_endpoint`**: full `https://…/…` URL from the phone's UnifiedPush distributor (for ntfy,
  `https://<server>/<topic>` where `<topic>` is the distributor topic, e.g. `upAbC…`, not an `hp-…` name).

Public keys are base64url (no padding) of the uncompressed SEC1 P-256 point (65 bytes, leading `0x04`).

## Registration

Over the authenticated dashboard connection only (`/mercurio-push register`; refused on messaging platforms).

Phone sends:

```json
{
  "device_id": "<uuid>",
  "name": "Pixel 9",
  "server": "https://ntfy.sh",
  "push_topic": "hp-…",
  "reply_topic": "hp-…",
  "enc_pub": "<b64u>",
  "sig_pub": "<b64u>",
  "push_endpoint": "https://ntfy.example/upTopicFromDistributor"
}
```

`push_endpoint` is optional. When omitted, the gateway POSTs sealed envelopes to `{server}/{push_topic}` as in
v1. When present:

- The gateway POSTs the envelope body to **`push_endpoint`** exactly (not `{server}/{push_topic}`).
- **`push_topic`** is still stored and still required; it identifies the logical g2p channel and legacy mode.
- **`reply_topic`** keeps the `hp-…` format and rules unchanged.

Gateway answers:

```json
{ "gateway_id": "<uuid>", "enc_pub": "<b64u>", "sig_pub": "<b64u>", "version": 1 }
```

### `push_endpoint` validation

- Scheme **`https`** only.
- No userinfo (`user:pass@` forbidden).
- Length ≤ **512** characters.
- Path must include a non-empty final segment (the distributor topic). The gateway never logs the full URL;
  logs use the host only.

### Updating the endpoint

`/mercurio-push update-endpoint` with JSON `{"device_id": "<uuid>", "push_endpoint": "<url>"}` or
`"push_endpoint": null` to revert to `{server}/{push_topic}`. Same trusted-surface rule as `register`.

## Envelope

One message body, at most **4096** bytes (plain `text/plain` POST).

```json
{
  "v": 1,
  "epk": "<b64u ephemeral P-256 pub>",
  "salt": "<b64u 16 bytes>",
  "iv": "<b64u 12 bytes>",
  "ct": "<b64u AES-256-GCM ciphertext||tag>",
  "sig": "<b64u DER ECDSA>"
}
```

**Topic binding (AAD and signature):** let `topic` be:

- `push_topic` when no `push_endpoint` is set, or
- the **last path segment** of `push_endpoint` after removing a trailing slash (e.g.
  `https://ntfy.sh/myTopic` → `myTopic`; `https://push.example/upAbCd` → `upAbCd`).

That `topic` string is AES-GCM additional authenticated data and appears in the signed message `M`:

1. `z = ECDH(ephemeral.priv, recipient.enc_pub)`
2. `key = HKDF-SHA256(ikm=z, salt=salt, info="herald-push/v1/" + dir, L=32)` where `dir` is `g2p` or `p2g`
3. `ct = AES-256-GCM(key, iv, plaintext, aad=topic)` (UTF-8 bytes of `topic`)
4. `sig = ECDSA-P256-SHA256(sender.sig_priv, M)` with  
   `M = "herald-push/v1|" + dir + "|" + topic + "|" + epk + "|" + salt + "|" + iv + "|" + ct`  
   (b64u field strings joined with `|`, UTF-8)

**Receiving:** verify signature before decrypt; decrypt with `aad=topic`; enforce `id`/`ts` replay rules as in
v1.

## Plaintext (`g2p` / `p2g`)

Same message types as Herald push v1 (`bot_message`, `approval`, `phone_request`, `phone_call`, `ping`, `chat_reply`,
`cron_run`, …). See Herald's document for field lists and watcher behaviour; Mercurio uses the same payloads
and the same `p2g` reservation (reply topics not read by the plugin yet).

## Commands (summary)

| Command | Purpose |
|---|---|
| `info` | Gateway keys, device count, plugin version |
| `register <json>` | Register or replace a phone |
| `update-endpoint <json>` | Set or clear `push_endpoint` |
| `unregister <device_id>` | Remove a phone |
| `test <device_id>` | Send `ping` |
| `phone …` / `cron …` | Phone tools and cron inbox (unchanged from herald-push) |
