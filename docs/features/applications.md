# 📦 Application provisioning

[← Features](README.md) · [How it works](../architecture.md)

Applications are installed during the [setup workflow](../setup.md).

## 🧰 Shared applications

Both profiles call [`install_common_apps`](../../src/apps.sh#L46-L66). It is the
single source of truth for the shared application list, packages, and
installation checks. The reusable
[installer helpers](../../src/apps.sh#L4-L44) skip existing applications and
CLIs before installing a missing Homebrew cask or formula.

## 👤 Personal-only applications

The personal profile calls
[`install_personal_apps`](../../src/apps.sh#L68-L78). The command-line tool with
a separate npm installation is defined by
[`install_desktop_commander_cli`](../../src/apps.sh#L80-L90).

To change the application inventory, edit [`src/apps.sh`](../../src/apps.sh)
and run the [development validation](../development.md#step-4--write-tests-and-run-them).
