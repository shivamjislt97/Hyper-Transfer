# rclone Google Drive Setup Guide

Step-by-step guide to configure rclone with Google Drive for the backup system.

---

## Prerequisites

Install rclone:
```bash
curl https://rclone.org/install.sh | sudo bash
```

---

## Step 1 — Start rclone config

```bash
rclone config
```

You will see an interactive menu. Type `n` and press Enter to create a new remote.

---

## Step 2 — Name the remote

```
name> gdrive
```

> Must match `RCLONE_REMOTE_NAME` in your `.env` file (default: `gdrive`).

---

## Step 3 — Choose storage type

A numbered list appears. Find and enter the number for **Google Drive**.

```
Storage> drive
```

---

## Step 4 — Client ID and Secret (leave blank for defaults)

```
client_id>        ← press Enter (leave blank)
client_secret>    ← press Enter (leave blank)
```

---

## Step 5 — Scope

```
scope> 1
```

Choose option `1` — full access to all files.

---

## Step 6 — Root folder ID (leave blank)

```
root_folder_id>   ← press Enter
```

---

## Step 7 — Service account (leave blank)

```
service_account_file>   ← press Enter
```

---

## Step 8 — Advanced config

```
Edit advanced config? n
```

---

## Step 9 — Auto config

```
Use auto config? y
```

rclone will open a browser window. Log in with your Google account and click **Allow**.

> If running on a headless server (no browser), answer `n` and follow the URL shown.

---

## Step 10 — Shared drive

```
Configure this as a Shared Drive (Team Drive)? n
```

---

## Step 11 — Confirm and quit

rclone shows the config summary. Type `y` to confirm, then `q` to quit.

---

## Verify it works

```bash
rclone lsd gdrive:
```

You should see your Google Drive folders listed.

---

## Test backup upload

```bash
SKIP_UPLOAD=0 bash docker-backup/backup.sh
```

Check Google Drive — you should see a folder: `Docker-Backups/Hyper-Transfer/`

---

## Config file location

rclone stores its config at:
```
~/.config/rclone/rclone.conf
```

To use a custom config path, set `RCLONE_CONFIG` environment variable or pass `--config` flag.
