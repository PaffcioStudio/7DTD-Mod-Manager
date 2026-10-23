If you run into any problems or bugs, please open an issue on GitHub. Include your app version, your Linux distro, and the relevant log from ~/.7dtd_modmanager/logs/.

## (latest) 1.0.46
- You can now see how long you have played each game instance and when it was last played. Instances that have never been started are clearly marked, and the page also shows your combined playtime.
- Playtime is measured while the game process is running, not when you simply press Launch. Progress is saved to disk, so it survives restarting the manager and can pick up a session that is still running.
- Cleaned up instance cards by moving technical paths, startup flags, and Proton information into a details tooltip. Playtime, installed mods, and launch controls are easier to spot.
- Added filters for favorites, played and unplayed instances, recently played instances, and the currently running game.
- Added sorting by creation date, last played, playtime, name, and enabled mods, with one-click reversal of the sorting direction.
- Added three ways to browse instances: a familiar grid, a compact list, and larger spotlight cards.
- Moved page descriptions underneath the page title in the top bar. Longer descriptions shorten gracefully and reveal their full text when hovered, rather than scrolling across the screen.
- Updated the Polish and English translations and added tests for playtime persistence, sorting, filtering, and the updated interface.
- Corrected the FAQ about application updates: startup checking is enabled by default, with a manual check available in Settings. Installing an update is still your choice.
- Expanded the Polish and English FAQ with practical answers about Steam authorization, downloading owned game releases, inaccessible mod files, compatibility, launching instances, playtime, logs, archives, updates, and backups.
- Improved the header search so it clearly shows matches from both your local mod library and 7daystodiemods.com, with website results labelled separately.
- Pressing Enter in the header search now opens online results in Discover instead of searching only your installed mods. You can also jump to all website matches from the search dropdown.
- Online search no longer inherits saved Discover provider, version, or category filters, so relevant mods are not silently hidden. A failed website request leaves local matches available, and cached online results are labelled when used.
- Added Polish and English text for the combined search and its online loading, cache, and empty states.
- Fixed cramped tooltips on instance cards. Long folder paths, launch flags, and Proton details now wrap neatly inside a readable popup.
- Added matching icons to the instance filter and sorting menus, including the currently selected option.
- Tidied the Instances toolbar: the New Instance button stays aligned to the right, while total playtime and the played-instance count sit together on the left.

## (old) 1.0.45
- Fixed downloads of V3 mods from 7daystodiemods.com when the installed Steam branch is `public`, `latest`, or `latest_experimental`. The file compatibility check now recognizes these as the V3 game family instead of rejecting them before making an API request.
- Fixed compatibility checks for human-readable catalog version labels, including `V3 Mods`, `V2 Mods`, and `Alpha 21`, without allowing files from other game families, and aligned the mod details drawer with the Steam experimental fallback alias.
- Improved diagnostic logging when no compatible hosted or external download can be found.
- Added regression tests for Steam branch aliases and catalog version matching.
- Fixed 7daystodiemods.com downloads of standalone POI prefabs such as `the shack`: a valid ZIP without `ModInfo.xml` can now be converted into a standard library modlet when it contains a matching `.xml` and `.tts` prefab pair.
- Added safe packaging under `Prefabs/POIs` with a valid generated `ModInfo.xml`, preserving companion prefab files and original archive contents. Prefabs remain controlled by the normal library activation system instead of overwriting the game's Data directory.
- Improved the error shown when a downloaded ZIP extracts successfully but contains neither installable mods nor a recognized POI prefab. Added a short archive content listing to diagnostics.
- Added tests for standalone and nested prefab archives, library installation, deduplication, and rejection of unsupported content.
- Reorganized the sidebar into five always-visible destinations (Dashboard, Instances, Mods, Discover, and Downloads) and collapsible **Game & Environment** (Steam Releases, Proton) and **Tools** (Profiles, Backups, Updates) groups, keeping Settings in the footer.
- Added smooth, theme-aware group expansion, preserved update badges and active-download indicators, and automatic group expansion when navigating via shortcuts, search, or other parts of the app.
- Persisted the expanded/collapsed state of both navigation groups across launches and added Polish and English group labels; small-window navigation now scrolls independently of the Settings and version footer.
- Updated the English screenshot capture script to include three deterministic sidebar previews (collapsed, Game & Environment expanded, and Tools expanded), while keeping the existing page captures and aliases. Screenshot sessions now read settings without saving navigation state or other preferences.

## (old) 1.0.44
- Added a screenshot gallery to the mod details drawer on **Discover**, above the download list. Arrow buttons on both sides switch between screenshots, and clicking an image opens a full-window preview inside the launcher (arrow keys, mouse wheel, and Esc supported), so mods can be browsed without visiting the website.
- Added app update checking against the GitHub release published under the fixed `release` tag. The release title is compared with the installed version; when a newer one exists, a dialog shows the release notes for the versions you are missing, with **Download** (opens the release page on GitHub) and **Cancel** (does nothing).
- Added a **Check for app updates on startup** option to Settings, enabled by default, plus a **Check now** button that reports when you are already on the latest version or when the check fails.
- Added Polish and English interface text for the update dialog and the new settings.

## (old) 1.0.43
- Added duplicate-mod checks before launching Steam installations and downloaded game copies. Instance mod versions take precedence; duplicate game descriptors are backed up outside `Mods` and restored when an instance no longer supplies the mod. Unsafe conflicts block launch without overwriting files.
- Added a persistent Proton version selector to instance creation and editing, with **Automatic** and explicit installed versions. Duplicated instances retain their selection, and missing selected versions block launch instead of silently falling back.
- Added a **Proton** page that discovers installed Steam and custom compatibility tools and downloads x86_64 GE-Proton releases from the author's repository. Downloads support progress, cancellation, SHA-512 verification, and installation into the manager's own data directory.
- Added removal of manager-installed Proton versions, with protection for versions assigned to instances and versions in use while the game is running.
- Added a **Logs** button to instance cards, with text previews and actions to open files or their folders. The viewer includes game logs, launcher logs, Proton debug logs, and Unity crash reports inside Wine prefixes, with shared-prefix reports clearly labelled.
- Enabled Proton debug logging for direct launches and stored `steam-251570.log` and `game-launch.log` in the instance's `logs` directory. Text previews display up to the last 256 KB of a file.
- Added the configured Proton version below the game version on each instance card, showing **Automatic** or the selected compatibility tool's name.
- Added Polish and English interface text for Proton management, instance selection, and log browsing.
- Matched the Proton page to Steam Releases with an installed-version grid, release rows, source information, status badges, and download progress panels.
- Reworked the English screenshot script to capture the real application with current local data and live services, without source-text replacements or permanent language changes. Added Proton, Steam Releases, and game-profile screenshots to the README gallery.
- Added case-insensitive Proton name search across installed versions and available releases, with result counts, empty-result messages, and Polish and English search text.

## (old) 1.0.42
- Fixed duplicate `anchors.topMargin` and `spacing` declarations on the Updates and Conflicts pages that could make QML page types unavailable at startup.
- Fixed missing Steam release page formatting helpers so installed and available branch sizes and dates render without QML runtime warnings.
- Fixed a QML layout syntax issue on the Downloads page that could prevent the main interface from loading.
- Fixed duplicate layout property declarations in the Discover page that could prevent the QML interface from loading.
- Kept the main window header compact by rendering page descriptions inside their respective sections instead of beside the page title, preventing long localized text from pushing account, search, settings, and window controls out of view.
- Fixed a startup issue on the Mods page caused by a duplicated layout property and cleaned up duplicate layout declarations in the Backups page.
- Restored the shared translated page metadata structure so backups and downloads retain consistent catalog-driven titles while their descriptive text remains inside the page content.
- Added a confirmation prompt before permanently removing a downloaded Steam release from local storage.
- Added a dedicated **Steam Releases** area for downloading and managing 7 Days to Die Steam branches without mixing branch management with instance configuration.
- Moved Steam branch downloads, authentication, retry, pause/resume, cancellation, progress, and DepotDownloader controls out of **Instances** and into **Steam Releases**.
- Clarified the separation between instance configuration, installed game branches, and active download operations to make the launcher easier to navigate and extend.
- Updated the interface text and navigation in Polish and English to consistently use **Steam Releases / Wydania Steam**.
- Updated the README and user-facing guidance so Steam branch management is documented under its dedicated area.
- Fixed download queue state handling so completed downloads are no longer displayed as active extraction jobs.
- Fixed retry handling for failed game-version downloads so a second attempt reuses the existing queue entry instead of creating a duplicate card.
- Added persistent download state for game-version downloads so active transfers can be resumed after restarting the launcher.
- Fixed game-version resume, pause, and cancel actions so they are handled by the game-version manager instead of the regular URL download worker.
- Added safe restoration of queued game-version downloads with preserved progress, size information, and branch metadata.
- Improved stale DepotDownloader handling to prevent abandoned download processes from interfering with retries and resumed transfers.
- Fixed completed-download history so individual completed entries can be removed directly from the Downloads page.
- Fixed progress precision for fractional download percentages instead of truncating values such as 12.5% to 12%.
- Improved download statistics layout with dedicated columns for downloaded size, transfer speed, and ETA.
- Prevented long localized ETA and status strings from overlapping neighboring download statistics.
- Improved handling of incomplete or previously failed download states so the UI reflects the actual operation state more reliably.
- Added MediaFire download support for external mod files.
- Fixed incorrect mod file selection when a mod provides downloads for multiple game versions.
- Improved version matching for externally hosted files, including MediaFire.
- Added **Undead Legacy** to the local overhaul catalog for game branch `v2.6`.
- Added dynamic Undead Legacy version detection from the official download table, so a new release does not require a hard-coded Dropbox URL in the manifest.
- Added stable `https://ul.subquake.com/dl?v=mirror` resolution at download time, keeping downloads pointed at the current mirror archive.
- Fixed Undead Legacy mirror downloads by assigning the mirror source to the regular ZIP download flow, avoiding a source-kind queue error.
- Fixed Undead Legacy download subtitle localization so internal i18n markers are no longer shown in the Downloads page.
- Fixed Undead Legacy mirror downloads so the final Dropbox request keeps the browser-style User-Agent and `https://ul.subquake.com/` Referer required by the current mirror response.
- Fixed successful Undead Legacy overhaul installs being reported as failed after instance creation because the temporary download directory was not initialized in the URL worker cleanup path.
- Fixed Undead Legacy downloads so the original ZIP is preserved in the launcher downloads directory and removed only by the existing archive cleanup settings.
- Fixed large overhaul downloads (e.g. Undead Legacy, ~7.5 GB) failing during extraction with `[Errno 28] No space left on device`: download and extraction now use a working directory inside the launcher data folder (`~/.7dtd_modmanager/tmp`) instead of the system `/tmp`, which is often a RAM-backed or small partition.
- Added free-disk-space checks before a ZIP transfer starts and before extraction begins (using the real uncompressed size from the archive), with a clear, translated message that shows the required and available space instead of a raw system error.
- Overhaul mod folders are now moved into the new instance instead of copied, so installation no longer needs a third full copy of the package on disk; when the working directory is on a different drive the free-space check runs first.
- Fixed retrying a failed download re-fetching the whole archive: a complete ZIP from the previous attempt is detected and reused, and a failed install no longer moves the ZIP out of the working directory before the instance is created.
- Failure to keep the Undead Legacy ZIP in downloads/ (for example no space) no longer marks an otherwise successful installation as failed.
- Added support for the BepInEx / Unity Doorstop loader shipped inside overhaul archives such as Undead Legacy (`winhttp.dll`, `doorstop_config.ini`, `BepInEx/`): the files are stored with the new instance and deployed next to `7DaysToDie.exe` on every launch, `WINEDLLOVERRIDES=winhttp=n,b` is added for Proton, and `[MultiFolderLoader] baseDir` is pointed at that instance's own `Mods/` folder.
- The shared game folder is cleaned automatically when an instance without the loader is launched, so vanilla and other instances on the same game version are not affected; only files recorded by the launcher are removed and any pre-existing file with the same name is backed up and restored.
- Native Linux and macOS Doorstop files from the archive (`run_bepinex*.sh`, `libdoorstop_*.so`, `libdoorstop.dylib`) are not used by the Proton launch and are not copied.
