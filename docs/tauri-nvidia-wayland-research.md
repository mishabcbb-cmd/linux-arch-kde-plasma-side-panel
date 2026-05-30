# Tauri 2 + NVIDIA + Wayland — Research & Solutions

**Date**: 2026-05-30
**Hardware**: NVIDIA GeForce RTX 3070, Driver 595.71.05
**Software**: KDE Plasma 6.6, WebKitGTK 2.52.3, Tauri 2.10.1
**Symptom**: `Gdk-Message: Error 71 (Protocol error) dispatching to Wayland display.`

---

## 1. Root Cause Analysis

### 1.1 The Core Problem

Tauri 2 on Linux uses **WebKitGTK** (not Chromium/Electron) for its web view. WebKitGTK 2.42+ uses a **DMA-BUF renderer** by default for accelerated compositing on Wayland. This renderer relies on:

- **GBM (Generic Buffer Management)** — for buffer allocation
- **DMA-BUF** — for zero-copy buffer sharing between GPU and compositor
- **Explicit Sync** — `wp_linux_drm_syncobj` protocol for GPU/CPU synchronization

NVIDIA's proprietary driver has **incomplete support** for these protocols:

| Protocol | NVIDIA Support | Issue |
|----------|---------------|-------|
| GBM | Partial | `Failed to create GBM buffer: Invalid argument` |
| DMA-BUF | Partial | `Error 71 (Protocol error)` — compositor rejects buffer |
| Explicit Sync | Added in 555+ | `explicit sync is used, but no acquire point is set` |

The specific error from `WAYLAND_DEBUG`:
```
wl_display#1.error(wp_linux_drm_syncobj_surface_v1#55, 4, "explicit sync is used, but no acquire point is set")
```

### 1.2 Why It Happens

1. WebKitGTK creates a DMA-BUF buffer via GBM
2. The buffer is passed to KWin compositor via Wayland protocol
3. KWin expects proper explicit sync synchronization points
4. NVIDIA's EGL/GBM implementation doesn't set the acquire point correctly
5. KWin rejects the buffer → `Error 71 (Protocol error)` → app crashes

### 1.3 Affected Configurations

- **GPUs**: All NVIDIA GPUs (RTX 30xx, 40xx, 50xx, GTX 10xx, etc.)
- **Drivers**: All proprietary NVIDIA drivers (555, 560, 565, 570, 575, 580, 590, 595+)
- **Compositors**: KWin (KDE Plasma 6), Mutter (GNOME 47+), Hyprland, Sway
- **WebKitGTK**: 2.42+ (DMA-BUF renderer introduced in 2.42)
- **Tauri**: All versions using WebKitGTK (Tauri 1.x, 2.x)

---

## 2. Researched Solutions (30+ Sources)

### 2.1 Solution Matrix

| # | Solution | Source | Works? | Side Effects | Performance |
|---|----------|--------|--------|--------------|-------------|
| 1 | `WEBKIT_DISABLE_DMABUF_RENDERER=1` | [WebKit Bug #280210](https://bugs.webkit.org/show_bug.cgi?id=280210), [Yaak](https://yaak.app/feedback/posts/fix-blank-screen-crash-on-linux-due-to-wayland-nvidia-etc), [Tauri #10702](https://github.com/tauri-apps/tauri/issues/10702) | ✅ Launch | Transparency broken, black corners | ⚠️ Slower (SHM fallback) |
| 2 | `__NV_DISABLE_EXPLICIT_SYNC=1` | [WebKit Bug #280210 comment](https://bugs.webkit.org/show_bug.cgi?id=280210#c6), [Tauri #9394](https://github.com/tauri-apps/tauri/issues/9394), [Yaak](https://yaak.app/feedback/posts/fix-blank-screen-crash-on-linux-due-to-wayland-nvidia-etc) | ✅ Launch | Ghosting artifacts on some setups | ✅ Good |
| 3 | `GSK_RENDERER=ngl` | [openSUSE Forum](https://forums.opensuse.org/t/gdk-message-error-71-protocol-error-dispatching-to-wayland-display/178886), [Arch BBS](https://bbs.archlinux.org/viewtopic.php?id=299488) | ⚠️ Partial | May not help alone | ✅ OpenGL |
| 4 | `GSK_RENDERER=gl` | [Tauri #14924](https://github.com/tauri-apps/tauri/issues/14924) | ⚠️ Partial | Ghosting possible | ✅ OpenGL |
| 5 | `GSK_RENDERER=cairo` | [Tauri #14924](https://github.com/tauri-apps/tauri/issues/14924) | ⚠️ Partial | Ghosting possible | ❌ Software |
| 6 | `WEBKIT_DISABLE_COMPOSITING_MODE=1` | [Yaak](https://yaak.app/feedback/posts/fix-blank-screen-crash-on-linux-due-to-wayland-nvidia-etc) | ✅ Launch | No GPU acceleration | ❌ Very slow |
| 7 | `GDK_GL=gles` | [hapax-council docs](https://github.com/hapax-systems/hapax-council/blob/main/docs/issues/tauri-wayland-protocol-error.md) | ⚠️ Unknown | Unknown | ⚠️ GLES only |
| 8 | Downgrade WebKitGTK to <2.42 | [Ubuntu LP#2041664](https://bugs.launchpad.net/bugs/2041664) | ✅ Works | Loses security updates | ⚠️ Old |
| 9 | Upgrade NVIDIA driver to 565+ | [Fedora Discussion](https://discussion.fedoraproject.org/t/gdk-message-error-71-protocol-error-dispatching-to-wayland-display/127927?page=3) | ✅ Fixed in 565+ | None | ✅ Best |
| 10 | Wait for upstream fix | [Tauri #14924](https://github.com/tauri-apps/tauri/issues/14924), [WebKit #261874](https://bugs.webkit.org/show_bug.cgi?id=261874) | ⏳ Pending | None | ⏳ Pending |

### 2.2 Recommended Solution (Priority Order)

**For NVIDIA 595+ driver (our case):**

1. **Primary**: `__NV_DISABLE_EXPLICIT_SYNC=1` — disables explicit sync in NVIDIA's EGL-Wayland layer, falls back to implicit sync. No visual artifacts reported on 595+.
2. **Secondary**: `GSK_RENDERER=ngl` — forces OpenGL renderer for GTK4 (not Vulkan which is broken on some NVIDIA configs).
3. **Fallback**: `WEBKIT_DISABLE_DMABUF_RENDERER=1` — disables DMA-BUF renderer entirely, falls back to SHM (slower but works).

**Combined (belt-and-suspenders):**
```bash
export __NV_DISABLE_EXPLICIT_SYNC=1
export GSK_RENDERER=ngl
export NVD_BACKEND=direct
export GDK_BACKEND=wayland
```

---

## 3. Sources (30 References)

### 3.1 WebKitGTK Bug Tracker

1. **[WebKit Bug #280210](https://bugs.webkit.org/show_bug.cgi?id=280210)** — `[GTK] Unable to start: Error 71 (Protocol error) dispatching to Wayland display`
   - Confirmed: `WEBKIT_DISABLE_DMABUF_RENDERER=1` fixes the issue
   - Root cause: `explicit sync is used, but no acquire point is set`
   - Affected: WebKitGTK 2.46.0, NVIDIA 560.35.03, Plasma 6.1.5, GNOME 47

2. **[WebKit Bug #261874](https://bugs.webkit.org/show_bug.cgi?id=261874)** — `REGRESSION(2.42): [GTK] GTK 3 rendering broken with 2.42 on NVIDIA graphics`
   - Status: RESOLVED MOVED
   - WebKit maintainer: "there really was either a WebKit or a NVIDIA bug here originally, but that's no longer the case with current WebKitGTK and NVIDIA driver versions"

3. **[WebKit Bug #280210 Comment #6](https://bugs.webkit.org/show_bug.cgi?id=280210#c6)** — `Setting __NV_DISABLE_EXPLICIT_SYNC=1 let's the application launch & also run smooth without low FPS`

### 3.2 Tauri GitHub Issues

4. **[tauri-apps/tauri#10702](https://github.com/tauri-apps/tauri/issues/10702)** — `[bug] Error 71 (Protocol error) dispatching to Wayland display`
   - 68 👍 reactions, 31 comments
   - Status: OPEN, labeled `upstream`
   - Workaround: `WEBKIT_DISABLE_DMABUF_RENDERER=1`

5. **[tauri-apps/tauri#9394](https://github.com/tauri-apps/tauri/issues/9394)** — `[docs] Documenting Nvidia problems in Tauri`
   - Comprehensive documentation of all NVIDIA issues
   - Lists all workarounds with trade-offs

6. **[tauri-apps/tauri#14924](https://github.com/tauri-apps/tauri/issues/14924)** — `[Bug] Linux/Nvidia: Crash (GBM/Error 71) or Visual Artifacts`
   - Detailed analysis of transparent window issue
   - Table of all workarounds and their side effects
   - Confirmed: `WEBKIT_DISABLE_DMABUF_RENDERER=1` breaks transparency

7. **[tauri-apps/tauri#12361](https://github.com/tauri-apps/tauri/issues/12361)** — `Rendering not working correctly with GDK_BACKEND=wayland`

8. **[tauri-apps/tauri#15050](https://github.com/tauri-apps/tauri/issues/15050)** — `[bug] Tauri 2 Blank Window on Fedora 43 + Sway (Wayland)`

9. **[tauri-apps/tauri#10626](https://github.com/tauri-apps/tauri/issues/10626)** — `Tauri 2.0.0-rc shows blank window after upgrading to webkit2gtk-4.1 2.44.3`

10. **[tauri-apps/tauri#12951](https://github.com/tauri-apps/tauri/issues/12951)** — `tauri web works, but app fails on archlinux`

11. **[tauri-apps/tauri#12431](https://github.com/tauri-apps/tauri/issues/12431)** — `linux development often show blank screen`

12. **[tauri-apps/tauri#9304](https://github.com/tauri-apps/tauri/issues/9304)** — `AppImage crashes on Linux`

13. **[tauri-apps/wry#1366](https://github.com/tauri-apps/wry/issues/1366)** — `Wry cannot create windows on Arch Linux with Nvidia`
    - Wry is the underlying web view library used by Tauri

### 3.3 Other Projects' Solutions

14. **[Dimillian/CodexMonitor](https://github.com/Dimillian/CodexMonitor)** — Auto-detects NVIDIA + Wayland in Rust:
    ```rust
    let has_nvidia = std::path::Path::new("/proc/driver/nvidia/version").exists();
    if is_wayland && has_nvidia && std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }
    ```

15. **[koala73/worldmonitor](https://github.com/koala73/worldmonitor)** — Same approach:
    ```rust
    unsafe { env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1"); }
    ```

16. **[DioxusLabs/dioxus](https://github.com/DioxusLabs/dioxus)** — Has `disable_dma_buf()` method in desktop module

17. **[farion1231/cc-switch](https://github.com/farion1231/cc-switch)** — Sets `WEBKIT_DISABLE_DMABUF_RENDERER` in `main.rs`

18. **[pot-app/pot-desktop](https://github.com/pot-app/pot-desktop)** — Documents the issue in README, recommends `WEBKIT_DISABLE_DMABUF_RENDERER=1`

19. **[cjpais/Handy](https://github.com/cjpais/Handy)** — Documents `WEBKIT_DISABLE_DMABUF_RENDERER=1` as troubleshooting step

20. **[xilec/RuVox](https://github.com/xilec/RuVox)** — Tech-debt tracker for monitoring upstream fix

### 3.4 Community Discussions

21. **[Yaak Feedback](https://yaak.app/feedback/posts/fix-blank-screen-crash-on-linux-due-to-wayland-nvidia-etc)** — Comprehensive troubleshooting guide with 48 comments

22. **[Reddit r/tauri](https://www.reddit.com/r/tauri/comments/16tzsi8/tauri_desktop_app_not_rendering_but_web_does/)** — Community workaround discussion

23. **[StackOverflow](https://stackoverflow.com/questions/79697769/tauri-black-window)** — `WEBKIT_DISABLE_DMABUF_RENDERER=1` solution

24. **[openSUSE Forum](https://forums.opensuse.org/t/gdk-message-error-71-protocol-error-dispatching-to-wayland-display/178886)** — `GSK_RENDERER=ngl` solution

25. **[Fedora Discussion](https://discussion.fedoraproject.org/t/gdk-message-error-71-protocol-error-dispatching-to-wayland-display/127927)** — Driver version discussion

26. **[Fedora Discussion (Minigalaxy)](https://discussion.fedoraproject.org/t/gdk-message-error-71-protocol-error-with-minigalaxy-on-fedora-41-nvidia-565-77/144658)** — `it fails because webkit2 does silly things and does not work well with wayland and explicit-sync enabled with NVIDIA drivers`

27. **[Arch BBS](https://bbs.archlinux.org/viewtopic.php?id=299488)** — `GTK 4.16.1 generates Wayland protocol error`

28. **[NVIDIA Developer Forum](https://forums.developer.nvidia.com/t/tauri-webkit2gtk4-1-apps-crash-on-launch-on-wayland/323726)** — Official NVIDIA thread

29. **[NVIDIA Developer Forum (560)](https://forums.developer.nvidia.com/t/560-release-feedback-discussion/300830/442)** — Driver release discussion

30. **[NVIDIA Developer Forum (DGX Spark)](https://forums.developer.nvidia.com/t/webkit-tauri-application-white-screen-on-dgx-spark-gpupermission-issues/348741)** — `WEBKIT_DISABLE_DMABUF_RENDERER=1 your-app`

### 3.5 Technical Deep-Dives

31. **[Xaver's Blog: Explicit Sync](https://zamundaaa.github.io/wayland/2024/04/05/explicit-sync.html)** — KDE developer explains explicit sync protocol

32. **[Phoronix: WebKitGTK DMA-BUF](https://www.phoronix.com/news/WebKitGTK-DMA-BUF-Rendering)** — Overview of DMA-BUF rendering evolution

33. **[itsfoss: Explicit Sync](https://itsfoss.com/news/explicit-sync-wayland/)** — Why explicit sync matters for NVIDIA

34. **[Collabora: Implicit-Explicit Sync](https://www.collabora.com/news-and-blog/blog/2022/06/09/bridging-the-synchronization-gap-on-linux/)** — Kernel-level sync interop

35. **[hapax-council docs](https://github.com/hapax-systems/hapax-council/blob/main/docs/issues/tauri-wayland-protocol-error.md)** — Detailed technical analysis

36. **[Wails v3 Changelog](https://v3.wails.io/changelog/)** — "Fix WebKitGTK crash on Wayland with NVIDIA GPUs (Error 71 Protocol error) by auto-disabling DMA-BUF renderer"

37. **[webkit2gtk-nvidia-quirk crate](https://docs.rs/webkit2gtk-nvidia-quirk/latest/webkit2gtk_nvidia_quirk/)** — Rust crate for automatic workaround

38. **[NVIDIA EGL-Wayland #179](https://github.com/NVIDIA/egl-wayland/issues/179)** — Explicit sync issue in NVIDIA's EGL-Wayland bridge

39. **[WPEWebKit #1573](https://github.com/WebPlatformForEmbedded/WPEWebKit/issues/1573)** — Photino application crashes due to explicit sync

40. **[KDE Bug #497424](https://bugs.kde.org/show_bug.cgi?id=497424)** — fd leak with explicit sync and KDE Plasma

---

## 4. Implementation

### 4.1 Rust Auto-Detection (Recommended)

Add to `src-tauri/src/lib.rs` before `tauri::Builder::default()`:

```rust
// Auto-detect NVIDIA + Wayland and apply workaround
#[cfg(target_os = "linux")]
{
    let is_wayland = std::env::var("XDG_SESSION_TYPE")
        .map(|s| s == "wayland")
        .unwrap_or(false);
    let has_nvidia = std::path::Path::new("/proc/driver/nvidia/version").exists();
    
    if is_wayland && has_nvidia {
        if std::env::var_os("__NV_DISABLE_EXPLICIT_SYNC").is_none() {
            std::env::set_var("__NV_DISABLE_EXPLICIT_SYNC", "1");
            log::info!("NVIDIA + Wayland detected: set __NV_DISABLE_EXPLICIT_SYNC=1");
        }
        if std::env::var_os("GSK_RENDERER").is_none() {
            std::env::set_var("GSK_RENDERER", "ngl");
            log::info!("NVIDIA + Wayland detected: set GSK_RENDERER=ngl");
        }
    }
}
```

### 4.2 Launch Script

```bash
export __NV_DISABLE_EXPLICIT_SYNC=1
export GSK_RENDERER=ngl
export NVD_BACKEND=direct
export GDK_BACKEND=wayland
cargo tauri dev
```

### 4.3 Persistent Configuration

**`/etc/environment`** (system-wide):
```
GSK_RENDERER=ngl
NVD_BACKEND=direct
GDK_BACKEND=wayland
```

**`~/.config/environment.d/gsk.conf`** (user session):
```
GSK_RENDERER=ngl
```

---

## 5. Verification

```bash
# Check env vars
echo $__NV_DISABLE_EXPLICIT_SYNC  # should print "1"
echo $GSK_RENDERER                # should print "ngl"
echo $GDK_BACKEND                 # should print "wayland"

# Check NVIDIA
cat /proc/driver/nvidia/version   # should show driver version

# Check session
echo $XDG_SESSION_TYPE            # should print "wayland"

# Launch
./scripts/tauri-wayland.sh
```

---

## 6. Future Outlook

- **NVIDIA 595+**: Explicit sync support added, but WebKitGTK may still need workaround
- **WebKitGTK 2.52+**: DMA-BUF renderer improvements ongoing
- **Tauri upstream**: Tracking in [#10702](https://github.com/tauri-apps/tauri/issues/10702), [#14924](https://github.com/tauri-apps/tauri/issues/14924)
- **KDE Plasma 6.6+**: Better explicit sync handling in KWin
- **Long-term**: Wait for full DMA-BUF + explicit sync support in NVIDIA driver + WebKitGTK

---

## 7. Changelog

| Date | Change |
|------|--------|
| 2026-05-30 | Initial research, 40 sources documented |
| 2026-05-30 | Created `scripts/tauri-wayland.sh` |
| 2026-05-30 | Updated `install.sh` with NVIDIA Wayland setup |
| 2026-05-30 | Updated `package.json` with `tauri:wayland` script |
| 2026-05-30 | Updated `/etc/environment` with NVIDIA Wayland vars |
| 2026-05-30 | Created `~/.config/environment.d/gsk.conf` |
