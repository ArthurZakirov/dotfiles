# 📦 Application provisioning

[← Features](README.md) · [How it works](../architecture.md)

Applications are installed during the [setup workflow](../setup.md).

## 🧰 Shared applications

Both profiles call [`install_common_apps`](../../src/apps.sh). It is the
single source of truth for the shared application list, packages, and
installation checks. The reusable
[installer helpers](../../src/apps.sh) skip existing applications and
CLIs before installing a missing Homebrew cask or formula.

[Peekaboo](peekaboo.md) and [agent-browser](agent-browser.md) also install their
official agent skills after the shared CLI provisioning completes.

## 👤 Personal-only applications

The personal profile calls
[`install_personal_apps`](../../src/apps.sh). The command-line tool with
a separate npm installation is defined by
[`install_desktop_commander_cli`](../../src/apps.sh).

To change the application inventory, edit [`src/apps.sh`](../../src/apps.sh)
and run the [development validation](../development.md#step-4--write-tests-and-run-them).
