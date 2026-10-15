# Optimus website

A static project page for Optimus Desktop with repository, contribution, and voluntary GitHub Sponsors links at **https://optimus.weeyuga.com/**, hosted on the existing Weeyuga server (`185.214.134.127`). The GitHub source repository is public under Apache 2.0. The desktop app remains experimental and untested in real projects; the CLI is confirmed usable.

Serve `dist/` with a static server to inspect the page. No payment system, account collection, tracking, or application credentials are included.

The desktop source is in `../../desktop/` when this page is included in the Optimus repository. Provider charges and local runtime prerequisites are explained on the page.

## Social previews

Open Graph and X large-image metadata are served directly in `dist/index.html`.
The branded sharing image is `dist/optimus-share-v1.png` (1200 × 630). All production
page/image references use absolute HTTPS URLs. Rebuild the image with
`python3 scripts/build-share-image.py` (Pillow plus Arial or DejaVu Sans required).
Use a new image filename when replacing it to avoid stale social-platform caches.
The page and image must be served without login or bot blocking.

## Hosting

DNS: A record `optimus.weeyuga.com` → `185.214.134.127`. No Sites deployment is used.
Upload only `dist/`, never the repository, local hosting metadata, credentials,
or desktop runtime. Releases live in `/srv/optimus.weeyuga.com/releases/`; nginx
serves the `current` symlink. Keep each release immutable and switch the symlink
to deploy or roll back.

Install `deploy/nginx-http.conf` for the first HTTP challenge, then issue a
dedicated certificate using Certbot's webroot `/var/www/letsencrypt` and the
existing registered ACME account. Install `deploy/nginx.conf` after certificate
issuance. Validate with `sudo nginx -t` before each reload. Existing vhosts and
certificates are independent. The existing Certbot timer handles renewal.

Verify HTTPS, HTTP→HTTPS redirection, every asset, crawler-user-agent fetches,
the returned HTML metadata, and the PNG dimensions. Verify the public GitHub
source and social links without requiring a signed-in account.

## Deployment evidence — 2026-10-14

- Server: `cicd`, `185.214.134.127`; HTTPS URL `https://optimus.weeyuga.com/`.
- Initial static release: `/srv/optimus.weeyuga.com/releases/20261014-web-v2`.
- Dedicated nginx vhost: `/etc/nginx/sites-available/optimus.weeyuga.com`.
- Dedicated Let's Encrypt certificate expires January 12, 2027. Certificate
  renewal simulation passed; `certbot.timer` is active. Renewal uses the HTTP
  webroot challenge, independent of the static-release symlink.
- HTTPS, HTTP-to-HTTPS redirect, all seven exact source assets, crawler-readable
  metadata, and the 1200×630 PNG passed live checks. Only the static website is
  served by nginx; credentials and local hosting metadata are not served. Source
  code is now separately available in the public GitHub repository.
- OpenGraph.xyz's external inspector returned zero errors and zero warnings,
  including a successful image fetch and the large-image X card configuration.
- Social-network caches can lag. Recheck actual X/Facebook cards after sharing;
  the configured image URL is versioned to support future cache refreshes.

To roll back content, atomically replace `current` with a symlink to a previous
release directory. The original HTTP vhost is backed up at
`/var/backups/optimus-website/20261014-initial/nginx-http.conf`; preserve HTTPS
when rolling back content. Future uploads must exclude macOS `._*` sidecar files.

On October 15, 2026, the desktop-testing notice was added to the live page.
Testing-notice release: `/srv/optimus.weeyuga.com/releases/20261015-testing-notice`.
The notice distinguishes the confirmed usable CLI from the experimental,
untested desktop workflows and invites bug reports and bug-fix pull requests.

## Public launch — 2026-10-15

The maintainer authorized public GitHub access. The launch page links to the
public source and retains the CLI/desktop testing notice. The footer uses the
same Weeyuga, Instagram, LinkedIn, X, Facebook and GitHub Sponsors destinations
as the AI Playbook site, with responsive styling in the Optimus palette.
Launch content release: `/srv/optimus.weeyuga.com/releases/20261015-public-launch`.
