# 7 Days To Die Mod Manager

A Linux desktop launcher and mod manager for **7 Days to Die**, built with Python, PySide6 and QML. Manage game releases from **Alpha 5 onward**, isolated instances, mods and overhauls in one application.

**Current version:** 1.0.50
**UI languages:** English (default) and Polish

## Screenshots

<table>
<tr>
<td align="center"><img src="docs/screenshots/dashboard-en.png" alt="Dashboard" width="100%"><br><sub>Dashboard</sub></td>
<td align="center"><img src="docs/screenshots/mods-en.png" alt="Mod library" width="100%"><br><sub>Mod library</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/screenshots/discover-en.png" alt="Discover" width="100%"><br><sub>Discover</sub></td>
<td align="center"><img src="docs/screenshots/backups-en.png" alt="Backups" width="100%"><br><sub>Backups</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/screenshots/updates-en.png" alt="Updates" width="100%"><br><sub>Updates</sub></td>
<td align="center"><img src="docs/screenshots/downloads-en.png" alt="Downloads" width="100%"><br><sub>Downloads</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/screenshots/profiles-en.png" alt="Profiles" width="100%"><br><sub>Profiles</sub></td>
<td align="center"><img src="docs/screenshots/conflicts-en.png" alt="Conflicts" width="100%"><br><sub>Conflicts</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/screenshots/settings-en.png" alt="Settings" width="100%"><br><sub>Settings</sub></td>
<td align="center"><img src="docs/screenshots/drawer-en.png" alt="Mod details drawer" width="100%"><br><sub>Mod details drawer</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/screenshots/steam-releases-en.png" alt="Steam releases" width="100%"><br><sub>Steam releases</sub></td>
<td align="center"><img src="docs/screenshots/protons-en.png" alt="Proton versions" width="100%"><br><sub>Proton versions</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/screenshots/game-profiles-en.png" alt="Game profiles" width="100%"><br><sub>Game profiles</sub></td>
<td></td>
</tr>
</table>

## Features

### Mod library

- Keep mods in a central library with version, author, source, game compatibility and update information.
- Import local folders, scan your Mods directory, and enable or disable mods for individual instances.
- Check for updates, install newer versions, open mod folders and remove mods from one place.
- Detect conflicting files and duplicate mods before launch. Supported standalone POI prefabs are packaged as modlets without changing the game's original prefab files.

### Isolated instances

- Create separate setups with their own mods, saves and game settings, and assign the required game release to each one.
- Rename, duplicate, edit and remove instances; keep favorites protected from accidental deletion.
- Select a game executable, Proton version and launch options for each instance.
- Track playtime and last played dates. Filter and sort instances, then browse them as a grid, list or spotlight cards.

### Steam releases and local imports

- Download and manage specific game branches from **Steam Releases**, using DepotDownloader and Steam Guard QR authorization.
- Browse 32 historical Alpha 5-8.8 releases with automatically selected Windows depots and manifests. Availability depends on Steam's current depot access.
- Keep downloaded game versions separate from the normal Steam installation and check the required version before launching a modded instance.
- Reinstall into a staging folder before replacing an existing copy, or uninstall a managed game release.
- Import an existing game folder as a historical release or under a custom name. Imports use symbolic links and check for duplicates; removing an import preserves the source files.

### Discover and search

- Browse the 7daystodiemods.com catalog and supported overhaul sources inside the launcher.
- Filter by category, game version, publication date and adult-content visibility.
- Sort by newest, featured, trending, recently updated, likes, downloads or views, and save your preferred filters.
- View descriptions, available files and screenshot galleries, with a full-window image preview.
- Search installed mods and instances from the header, see online matches, or press Enter to open the full website search in Discover.

### Modpacks and overhauls

- Install supported packages from Git repositories, GitHub releases, direct archive links and supported external hosts, including public Google Drive files.
- Extract ZIP, 7z and RAR archives, including supported packages whose mod files sit directly at the archive root.
- Create dedicated overhaul instances with the matching game version and supported bundled loaders, including BepInEx/Unity Doorstop.
- Reuse cached archives when available and check game-version compatibility before installation.

### Downloads and updates

- Manage game downloads, mods and mod updates in a shared queue with progress, transfer speed and estimated time remaining.
- Pause, resume, cancel and retry supported downloads. Keep download history and recover interrupted game downloads after restarting the manager.
- Download a missing game version after confirmation, while its mod waits in the queue.
- Check mods for updates and receive application update notifications with release notes and a link to the release page.

### Proton and logs

- Discover installed Steam and custom Proton versions, or download GE-Proton with SHA-512 verification.
- Choose automatic Proton selection or an explicit version for each instance.
- Remove manager-installed Proton versions while protecting versions assigned to instances.
- Preview game, launcher and Proton logs, inspect Unity crash reports, and open their files or folders from an instance card.

### Backups and profiles

- Back up instance mods, saves and data, then refresh, restore or delete backups from a dedicated page.
- Restore a backup even after its original instance has been removed, with checks for unsafe paths and running games.
- Manage supported V3+ game profiles, assign them to instances or make them available globally.

### Interface and customization

- Switch between English and Polish without restarting the application.
- Choose Dark, Light, Stalker or Stalker Light themes, with configurable UI scaling, animations and dashboard artwork.
- Use collapsible sidebar groups that remember their state, with quick access to downloads, settings and account controls.

## Requirements

- **Linux** with a graphical desktop.
- **Python 3.12** and virtual-environment support for running from source or building packages.
- **PySide6 >= 6.10, < 7.0**, **requests** and **Pillow**, installed automatically by `venv.sh` into the local `.venv`.
- A **Steam account with access to 7 Days to Die** for authenticated game downloads, and **Proton** for launching downloaded Windows releases.
- **Git** for Git-based modpack sources; **libarchive** for 7z/RAR extraction. Debian packages declare the libarchive dependency; source and AppImage users need it installed on the host.
- For packaging: **rsync**, **dpkg-deb**, **curl** and **python3**. The build script downloads `appimagetool` when needed.

On recent Ubuntu/Tuxedo OS, install libarchive with `sudo apt install libarchive13t64`; older releases use `libarchive13`.

## Run from source

Download and extract the repository, then run from its root directory:

```bash
./venv.sh
./run.sh
```

The setup script creates `.venv` and installs `requirements.txt`. Run the automated tests with:

```bash
./test.sh
```

## Build packages

Build Debian and AppImage packages into `dist/`:

```bash
./build.sh
```

To build and install or update the Debian package in one step:

```bash
./build.sh --install
```

For manual Debian installation, replace the version and architecture in:

```bash
sudo apt install ./dist/7dtd-mod-manager_<version>_<arch>.deb
```

Packages bundle the Python environment. Each build clears the previous contents of `dist/`.

## Steam login and first launch

1. Open **Steam Releases** or click the account icon in the header to start Steam authorization.
2. Scan the QR code with the Steam mobile app and approve the sign-in. The manager reuses the saved session; the account menu offers **Sign in again** and **Sign out**.
3. Download the game release required by your mods. Historical releases select their depot and manifest automatically; Steam still controls access to each release.
4. Create an instance, select its game version and Proton, then add mods through **Discover** or import local files. The normal Steam installation remains a separate game source.

Steam login is needed for authenticated game downloads. Third-party mod hosts may have their own access requirements; signing in to Steam does not unlock their files.

### If a historical release cannot be downloaded

**Steam Releases → Download with a Steam code** accepts `AppID DepotID ManifestID`, for example `251570 251576 1730022800995997518`, without the `download_depot` prefix. Share these three numbers so other launcher users can download the same release. A code matching the catalog uses its existing release entry; other manifests get a separate folder under `~/.7dtd_modmanager/game-versions/` and are registered in `game-versions.json` after a successful, validated download. Downloads use the shared queue with pause and resume. Only 7 Days to Die Windows releases are supported, and a code does not bypass Steam's ownership or manifest-access checks.

Alpha 6.0-6.4 currently fail with `Depot 251574 not listed for app 251570`. This indicates that depot `251574` is not associated with application `251570` in the Steam data visible to the account. DepotDownloader refuses to continue before downloading the manifest. This result does not prove that the manifests or game files have been physically removed from Steam's servers. If you already have a local copy, use **Import folder**.

## Data and support

Settings, game downloads, mods, backups and logs are stored under `~/.7dtd_modmanager/`. Use an instance's **Logs** button for game and Proton diagnostics.

For help, see **Settings → About → FAQ**. Report bugs through GitHub Issues with the application version, Linux distribution and relevant logs from `~/.7dtd_modmanager/logs/`.

## License and credits

Created by [PaffcioStudio](https://github.com/paffciostudio). Licensed under the [MIT License](LICENSE).

This is an independent community project, not affiliated with The Fun Pimps. Discover uses the public catalog of [7daystodiemods.com](https://7daystodiemods.com); mods and their content belong to their respective authors.
