# OpenSSH LAN Setup

Current machine LAN address: `192.168.1.10`

OpenSSH client is installed. The OpenSSH server is not installed yet, and port 22 is not listening. Installation requires local sudo authentication.

## Setup

From the project root, run:

```bash
chmod +x scripts/setup_openssh_lan.sh
LAN_CIDR=192.168.1.0/24 ./scripts/setup_openssh_lan.sh
```

The script:

1. Installs `openssh-server`.
2. Enables and starts the `ssh` systemd service.
3. Allows TCP port 22 from the private `192.168.1.0/24` LAN when UFW is installed.
4. Prints the machine's LAN address.

## Connect from another LAN device

```bash
ssh aryan@192.168.1.10
```

Use the actual username and LAN address printed by the script.

## Verify

On this machine:

```bash
systemctl status ssh
ss -tlnp | grep ':22'
```

From the other device:

```bash
ssh -v aryan@192.168.1.10
```

## Key-based login

Generate a key on the client device, not in the repository:

```bash
ssh-keygen -t ed25519 -C "legalagent-lan"
ssh-copy-id aryan@192.168.1.10
```

Then test:

```bash
ssh aryan@192.168.1.10
```

Only after key login works should password login be disabled. Do not disable password authentication before confirming the key works, or you may lock yourself out.

## Security boundaries

- Keep SSH restricted to the private LAN; do not forward port 22 from the router.
- Use a strong local account password until key login is verified.
- Never commit private keys, `.env`, or credentials.
- If the LAN is untrusted, use a narrower CIDR or a VPN instead.
