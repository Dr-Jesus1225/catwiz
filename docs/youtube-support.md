# YouTube extraction support

CatWiz prepares the YouTube extraction dependencies in the same Python environment
used to run CatWiz:

- `yt-dlp[default]` supplies yt-dlp and its matching `yt-dlp-ejs` challenge scripts.
- Deno 2.3 or newer runs the EJS JavaScript challenge solver.
- `bgutil-ytdlp-pot-provider` supplies PO tokens through the BgUtils provider.
- The BgUtils provider source is installed under
  `~/bgutil-ytdlp-pot-provider`; its Deno dependencies are installed from
  the repository's `server` directory.
- CatWiz enables yt-dlp's `ejs:github` remote-component fallback and prefers
  the `mweb` player client, following yt-dlp's current PO-token guidance.
- Browser cookies remain optional and are not required to generate anonymous
  PO tokens.

The BgUtils generation-script mode is used rather than a background HTTP
service. This avoids opening a local network port or maintaining a daemon.
It has more per-extraction overhead, but CatWiz's normal workflow processes
playlist items sequentially.

## Diagnostics

Open CatWiz's Logs page or inspect the diagnostic log for the
`youtube-setup` component. A successful setup records
`YouTube challenge solver and PO-token provider are ready`.

To verify provider discovery manually, run the CatWiz Python interpreter with
yt-dlp verbose diagnostics and look for BgUtils PO Token Providers in the
YouTube extractor output.

## Limitations

YouTube changes its challenge and attestation systems regularly. A working
Deno/EJS solver and PO-token provider materially improve compatibility, but
cannot guarantee every video is accessible. Private, deleted, age-restricted,
region-restricted, account-gated, or IP-blocked videos may still fail. The
BgUtils project itself explicitly cautions that a PO token does not guarantee
avoidance of HTTP 403 errors or bot checks.

References:
- https://github.com/yt-dlp/yt-dlp/wiki/EJS
- https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
- https://github.com/Brainicism/bgutil-ytdlp-pot-provider
