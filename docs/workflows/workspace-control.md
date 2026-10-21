# Control windows, displays, and multiple Macs

[← DevMac](../../README.md) · [Feature index](../features/README.md)

When switching windows, monitors, or Macs takes too much effort, you may stop switching at all and keep working around what's already open. These shortcuts make the workspace you need easy to reach, whether it's on the same display, another monitor, or another computer.

## Window navigation works even with one display

| Task | Tool | What it contributes |
| --- | --- | --- |
| Find a window among open applications | **AltTab** | A visual window switcher |
| Snap or resize a window | **Rectangle** | Common single- or multi-screen placements |
| Move, focus, or find windows via hotkeys | [**Hammerspoon**](../features/hammerspoon.md) | Managed bindings for tiling, window picking, and application actions |
| Switch Spaces without navigating Mission Control manually | [**Hammerspoon**](../features/hammerspoon.md) | Managed previous/next Space and window-move bindings |
| Customize native application/system shortcuts | [**macOS shortcuts**](../features/macos-shortcuts.md) | Managed preferences and a VS Code diff of shortcut changes |

AltTab, Rectangle, and the native shortcut system overlap in *purpose*, not necessarily implementation. Their tools complement different actions rather than forming a single integrated window manager.

## Make a multi-monitor workspace usable

| Need | Tool | Scope / limitation |
| --- | --- | --- |
| Move a focused window to another monitor, or focus that monitor | [Hammerspoon](../features/hammerspoon.md) | Configured display numbers depend on your physical layout |
| Run additional monitors through compatible display adapters/docks | **DisplayLink Manager** | Requires DisplayLink-compatible hardware and platform permissions |
| Improve text readability and access display scaling options | **BetterDisplay** | Display settings and available modes depend on hardware |
| Arrange or resize a window on any connected monitor | **Rectangle / Hammerspoon** | Works on one monitor too; this is not exclusively multi-monitor tooling |

## Work across separate computers

| Need | Tool | How it helps |
| --- | --- | --- |
| Switch a shared Dell display between connected computers | **Dell Display and Peripheral Manager (DDPM)** | Supports monitor input switching where the monitor and app permit it; configure shortcuts on each Mac |
| Move pointer/keyboard control between computers and use compatible cross-computer clipboard/file workflows | **Logi Options+ / Flow** | Requires supported Logitech hardware, network connectivity, and individual setup |
| Carry your chosen configs and shortcuts between Macs | **Git + chezmoi** | Versioned, deliberate review and apply—not automatic live synchronization |

These solve different parts of the **multi-Mac experience**: monitor input selection, peripheral/clipboard movement, and configuration portability. DDPM shortcuts and Flow connections still require compatible devices and individual setup; configuration updates are explicitly reviewed and applied.

## Keep the setup you have built

Losing access to a computer should not mean losing the tools and configurations you've spent hundreds of hours refining.

Your job can end unexpectedly or as planned. Your Mac can break, get stolen, or be forgotten somewhere. You might upgrade to a new machine. In each case, starting from scratch means reinstalling tools and rebuilding your workflow—potentially spending weeks or months recovering your former productivity.

With [Git and chezmoi](../setup.md), improvements made on one Mac can be committed and applied to another, and a replacement Mac can restore an established setup. Synchronization is explicit, not automatic in the background.

## Installation and configuration details

The [tool inventory](../tool-inventory.md) distinguishes installed third-party applications from DevMac's own scripts and configured hotkeys. Consult the [setup guide](../setup.md) before applying to an existing Mac, especially one with working display or shortcut customizations.
