# CatWiz

## Features

- Audio (.mp3, 128 to 320 kbps), video (.mp4, pick your resolution), or thumbnail (.png)
- Single links or full playlists
- Works with `youtube.com`, `music.youtube.com`, `youtu.be`, `youtube.com/shorts`, and `youtube.com/playlist`
- Keeps metadata, cover art, and chapters in your files

## Install

Copy the command for your system and paste it into your terminal.

It needs Git, Python, FFmpeg, and yt-dlp.

### Termux

```bash
pkg install -y curl && bash -c "$(curl -fsSL https://raw.githubusercontent.com/Dr-Jesus1225/catwiz/main/install.sh)"
```

Allow storage access when Termux asks, so downloads can be saved to your phone.

### Debian/Ubuntu

```bash
sudo apt-get update && sudo apt-get install -y curl && bash -c "$(curl -fsSL https://raw.githubusercontent.com/Dr-Jesus1225/catwiz/main/install.sh)"
```

### macOS

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Dr-Jesus1225/catwiz/main/install.sh)"
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/Dr-Jesus1225/catwiz/main/install.ps1 | iex
```

## Usage

On Termux, Debian/Ubuntu, and macOS, type `catwiz` to start.

On Windows use the `catwiz` command. Alternatively, run:

```powershell
py "$HOME\CatWiz\main.py"
```

## Default storage location

| System | Folder |
| --- | --- |
| Android | `/storage/emulated/0/Download/CatWiz` |
| Windows | `C:\Users\(your-username)\Downloads\CatWiz`  |

## Uninstall

Open the program, choose `-1. Settings`, then `1. Uninstall CatWiz`.

It removes the program folder and the `catwiz` shortcut. It then lets you choose whether to also remove FFmpeg, yt-dlp, Python, and Git, whether or not this program installed them, and shows roughly how much space that frees. Your downloaded files are never deleted.

Some programs are left out on purpose. On Debian/Ubuntu, Python is not offered, because system tools depend on it. On Debian/Ubuntu and macOS, yt-dlp lives inside the program folder and goes away with it.

## Updating

Run the install command again and it will pull the latest version. If downloads stop working, update yt-dlp by running the install command again.

## Disclaimer

Only download content you have the right to download, and follow YouTube's terms of service.


